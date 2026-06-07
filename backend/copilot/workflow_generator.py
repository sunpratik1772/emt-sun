"""
dbSherpa Copilot — workflow generation via the agent harness.

Free-form chat uses GeminiAdapter directly. Workflow draft/repair runs
through AgentRunner (classify → retrieve → generate → validate → auto-fix
→ repair loop → runtime smoke).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from llm import GeminiAdapter, get_default_adapter
from runtime_env import ensure_env_loaded

from generation.harness.runner import AgentRunner
from generation.harness.state import AgentPhase, AgentState
from generation.prompt_builder import PromptBuilder
from generation.harness.memory import MemoryManager
from generation.harness.retriever import ContextRetriever

from .intent_router import CopilotIntentResult, classify_copilot_intent
from .thread_context import (
    append_thread_turn,
    format_thread_context,
    resolve_thread_history,
)
from .agent_sse_adapter import AgentSseAdapter
from .binding_diagnosis import diagnose_binding_issues, format_binding_diagnosis_markdown
from .run_analyst import (
    stream_generation_failure_summary,
    stream_workflow_design_summary,
    stream_run_execution_summary,
)


class WorkflowCopilot:
    def __init__(
        self,
        skills_dir: str = "skills",
        contracts_path: str = "contracts/node_contracts.json",
        llm: GeminiAdapter | None = None,
        runner: AgentRunner | None = None,
    ) -> None:
        ensure_env_loaded()
        self.skills_dir = Path(skills_dir)
        self.contracts_path = Path(contracts_path)
        self._llm = llm or get_default_adapter()
        self._prompt_builder = PromptBuilder(
            skills_dir=self.skills_dir,
            contracts_path=self.contracts_path,
        )
        self._memory = MemoryManager()
        self._retriever = ContextRetriever(memory=self._memory)
        self._runner = runner or AgentRunner(
            prompt_builder=self._prompt_builder,
            memory=self._memory,
            retriever=self._retriever,
        )
        self._histories: dict[str, list[dict]] = {}
        self._last_workflow: dict | None = None
        self._last_validation: dict | None = None

    def resolve_session_thread(
        self,
        session_id: str | None,
        *,
        thread_messages: list[dict] | None = None,
        db_messages: list[dict] | None = None,
    ) -> list[dict[str, str]]:
        return resolve_thread_history(
            self._histories,
            session_id,
            thread_messages=thread_messages,
            db_messages=db_messages,
        )

    @staticmethod
    def thread_context_from_history(history: list[dict] | None) -> str:
        return format_thread_context(history)

    def record_thread_turn(
        self,
        session_id: str | None,
        *,
        user_message: str,
        assistant_message: str,
    ) -> None:
        append_thread_turn(
            self._histories,
            session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    def chat(
        self,
        user_message: str,
        *,
        session_id: str | None = None,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        planning_monologue: str | None = None,
    ) -> str:
        history = self._histories.setdefault(session_id, []) if session_id else []
        user_turn = self._format_chat_turn(
            user_message,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            planning_monologue=planning_monologue,
        )
        reply = self._llm.chat_turn(
            system_prompt=self._prompt_builder.chat_system_prompt(),
            history=history,
            user_turn=user_turn,
            temperature=0.3,
            json_mode=False,
        )
        issues = diagnose_binding_issues(
            user_message=user_message,
            workflow=current_workflow,
        )
        diag = format_binding_diagnosis_markdown(issues)
        if diag and diag not in reply:
            reply = f"{diag}\n\n{reply}"
        from copilot.next_action import ensure_ask_next_action_footer

        reply = ensure_ask_next_action_footer(
            reply,
            user_message=user_message,
            workflow=current_workflow,
        )
        if session_id:
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": reply})
        return reply

    @staticmethod
    def _format_chat_turn(
        user_message: str,
        *,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        planning_monologue: str | None = None,
    ) -> str:
        parts: list[str] = []
        if (planning_monologue or "").strip():
            parts.append(
                "[Sherpa planning — binding; your answer must follow this plan]\n"
                f"{planning_monologue.strip()}"
            )
        parts.append(user_message.strip())
        if current_workflow:
            wf_name = current_workflow.get("name") or current_workflow.get("workflow_id") or "Untitled"
            node_count = len(current_workflow.get("nodes") or [])
            edge_count = len(current_workflow.get("edges") or [])
            parts.append(
                f"\n\n[Canvas context]\nWorkflow: {wf_name}\nNodes: {node_count}\nEdges: {edge_count}"
            )
            nodes = current_workflow.get("nodes") or []
            if nodes:
                summary_lines = []
                for node in nodes[:24]:
                    if not isinstance(node, dict):
                        continue
                    summary_lines.append(
                        f"- {node.get('id', '?')}: {node.get('type', '?')} — {node.get('label', '')}"
                    )
                parts.append("Node summary:\n" + "\n".join(summary_lines))
        if recent_errors:
            err_lines = []
            for err in recent_errors[:12]:
                if not isinstance(err, dict):
                    continue
                node_id = err.get("node_id") or "workflow"
                message = err.get("message") or str(err)
                err_lines.append(f"- [{err.get('kind', 'error')}] {node_id}: {message}")
            if err_lines:
                parts.append("\n[Recent errors]\n" + "\n".join(err_lines))
        binding = format_binding_diagnosis_markdown(
            diagnose_binding_issues(
                user_message=user_message,
                workflow=current_workflow,
            )
        )
        if binding:
            parts.append("\n" + binding)

        # Match UA context for Chat Mode (Ask Mode)
        import os
        if os.environ.get("DBSHERPA_ENABLE_UA_CONTEXT", "1").lower() in {"1", "true", "yes"}:
            try:
                from app.understand_anything import load_ua_bundle
                bundle = load_ua_bundle()
                if bundle and bundle.get("available"):
                    domain_graph = bundle.get("domainGraph") or {}
                    nodes = domain_graph.get("nodes", [])
                    if nodes:
                        query_terms = set(user_message.lower().split())
                        if current_workflow:
                            query_terms.update(str(current_workflow.get("name", "")).lower().split())
                            query_terms.update(str(current_workflow.get("description", "")).lower().split())
                        query_terms = {t for t in query_terms if len(t) > 2}
                        
                        matched_domains = []
                        matched_flows = []
                        matched_steps = []
                        
                        for node in nodes:
                            ntype = node.get("type")
                            name = str(node.get("name", "")).lower()
                            summary = str(node.get("summary", "")).lower()
                            tags = [t.lower() for t in node.get("tags", [])]
                            
                            name_terms = set(name.split())
                            summary_terms = set(summary.split())
                            
                            has_term_match = bool(query_terms & name_terms) or bool(query_terms & summary_terms)
                            has_tag_match = any(t in query_terms for t in tags)
                            
                            if has_term_match or has_tag_match:
                                if ntype == "domain":
                                    matched_domains.append(node)
                                elif ntype == "flow":
                                    matched_flows.append(node)
                                elif ntype == "step":
                                    matched_steps.append(node)
                                    
                        ua_blocks = []
                        if matched_domains:
                            ua_blocks.append("Matching Domains:")
                            for dom in matched_domains[:3]:
                                ua_blocks.append(f"- Domain: {dom.get('name')} ({dom.get('id')})")
                                ua_blocks.append(f"  Summary: {dom.get('summary')}")
                        if matched_flows:
                            ua_blocks.append("Matching Flows:")
                            for flow in matched_flows[:4]:
                                ua_blocks.append(f"- Flow: {flow.get('name')} ({flow.get('id')})")
                                ua_blocks.append(f"  Summary: {flow.get('summary')}")
                        if matched_steps:
                            ua_blocks.append("Matching Code Steps/Files:")
                            for step in matched_steps[:6]:
                                path_str = f" in {step.get('filePath')}" if step.get("filePath") else ""
                                ua_blocks.append(f"- Step: {step.get('name')}{path_str}")
                                ua_blocks.append(f"  Summary: {step.get('summary')}")
                                
                        if ua_blocks:
                            parts.append(
                                "\n[Understand-Anything Codebase Context]\n"
                                + "\n".join(ua_blocks)
                            )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to retrieve UA context for chat: {e}")

        return "\n".join(parts)

    def classify_intent(
        self,
        message: str,
        *,
        has_workflow: bool = False,
        workflow_name: str | None = None,
        has_run_log: bool = False,
        run_id: str | None = None,
        run_workflow_name: str | None = None,
        recent_errors: list[dict] | None = None,
        thread_context: str | None = None,
        recent_run_workflows: list[str] | None = None,
        canvas_workflow: dict | None = None,
    ) -> CopilotIntentResult:
        return classify_copilot_intent(
            message,
            has_workflow=has_workflow,
            workflow_name=workflow_name,
            has_run_log=has_run_log,
            run_id=run_id,
            run_workflow_name=run_workflow_name,
            recent_errors=recent_errors,
            thread_context=thread_context,
            recent_run_workflows=recent_run_workflows,
            canvas_workflow=canvas_workflow,
            adapter=self._llm,
        )

    def route_sherpa(
        self,
        message: str,
        **kwargs,
    ):
        from copilot.llm_router import route_sherpa_message

        return route_sherpa_message(message, adapter=self._llm, **kwargs)

    def reset(self, *, session_id: str | None = None) -> None:
        if session_id:
            self._histories.pop(session_id, None)
        else:
            self._histories.clear()

    def generate_with_critic(
        self,
        user_request: str,
        iterations: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
        compiler_mode: str = "harness",
        session_id: str | None = None,
        thread_messages: list[dict] | None = None,
        db_messages: list[dict] | None = None,
    ) -> dict:
        history = self.resolve_session_thread(
            session_id,
            thread_messages=thread_messages,
            db_messages=db_messages,
        )
        thread_context = self.thread_context_from_history(history)
        state = self._runner.run(
            user_request,
            max_attempts=max(1, int(iterations)),
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
            thread_context=thread_context or None,
        )
        result = self._result_from_state(state, compiler_mode=compiler_mode)
        if result.get("workflow"):
            self._last_workflow = result["workflow"]
        self._last_validation = result.get("validation")
        self._record_generation_turn(session_id, user_request, state, result)
        return result

    def generate_with_critic_stream(
        self,
        user_request: str,
        iterations: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
        compiler_mode: str = "harness",
        session_id: str | None = None,
        thread_messages: list[dict] | None = None,
        db_messages: list[dict] | None = None,
    ) -> Iterator[dict]:
        history = self.resolve_session_thread(
            session_id,
            thread_messages=thread_messages,
            db_messages=db_messages,
        )
        thread_context = self.thread_context_from_history(history)
        intent = classify_copilot_intent(
            user_request,
            has_workflow=current_workflow is not None,
            recent_errors=recent_errors,
            thread_context=thread_context or None,
            adapter=self._llm,
        )
        if intent.intent == "ask":
            yield {"type": "thinking", "step": "Understanding your question", "status": "running"}
            try:
                reply = self.chat(
                    user_request,
                    session_id=session_id,
                    current_workflow=current_workflow,
                    recent_errors=recent_errors,
                ) or ""
            except Exception as exc:
                yield {"type": "error", "message": str(exc)}
                yield {"type": "done", "success": False, "compiler_mode": compiler_mode}
                return
            yield {"type": "thinking", "step": "Understanding your question", "status": "done"}
            yield {"type": "text_start"}
            for chunk in _chunk_run_text(reply):
                yield {"type": "text_chunk", "chunk": chunk}
            yield {"type": "text_end"}
            yield {"type": "done", "success": True, "compiler_mode": compiler_mode, "intent": "answer_question"}
            return

        adapter = AgentSseAdapter(user_request=user_request)
        final_state: AgentState | None = None

        for event in self._runner.stream(
            user_request,
            max_attempts=max(1, int(iterations)),
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
            thread_context=thread_context or None,
        ):
            if event.phase == AgentPhase.COMPLETE:
                final_state = _state_from_complete_event(
                    event,
                    scenario=user_request,
                    max_attempts=max(1, int(iterations)),
                )
                continue
            for frame in adapter.convert(event):
                yield frame

        if final_state is None:
            yield {"type": "error", "message": "Generation failed"}
            yield {"type": "done", "success": False, "compiler_mode": compiler_mode}
            return

        result = self._result_from_state(final_state, compiler_mode=compiler_mode)
        if result.get("workflow"):
            self._last_workflow = result["workflow"]
        self._last_validation = result.get("validation")

        if final_state.is_valid and isinstance(final_state.workflow, dict):
            for frame in adapter._workflow_created_events(final_state.workflow):
                yield frame

            yield {"type": "thinking", "step": "Explaining workflow design", "status": "running"}
            
            for chunk in stream_workflow_design_summary(
                final_state.workflow,
                user_request,
            ):
                for frame in adapter.emit_text_chunk(chunk):
                    yield frame
            
            for frame in adapter.emit_text_end():
                yield frame
                
            yield {"type": "thinking", "step": "Explaining workflow design", "status": "done"}
            adapter.mark_explanation_sent()
        elif not final_state.is_valid:
            from copilot.thinking_monologue import ThinkingMonologueContext
            from copilot.next_action import ensure_failure_next_action_footer
            from copilot.thinking_sse import yield_llm_thinking_monologue

            failure_payload = {
                "user_request": user_request,
                "draft_workflow": final_state.workflow if isinstance(final_state.workflow, dict) else None,
                "validation_errors": final_state.errors,
                "runtime_smoke_error": final_state.runtime_smoke_error,
                "auto_fixes_applied": final_state.auto_fixes_applied,
            }
            ctx = ThinkingMonologueContext.for_failure(user_request, failure_payload)
            monologue = ""
            for frame in yield_llm_thinking_monologue(ctx):
                monologue = str(frame.get("detail") or monologue)
                yield frame

            failure_parts: list[str] = []
            for chunk in stream_generation_failure_summary(
                user_request,
                errors=final_state.errors,
                warnings=final_state.warnings,
                workflow=final_state.workflow if isinstance(final_state.workflow, dict) else None,
                runtime_smoke_error=final_state.runtime_smoke_error,
                auto_fixes_applied=final_state.auto_fixes_applied,
                attempts=final_state.attempts,
                step_budget_hit=final_state.step_budget_hit,
                planning_monologue=monologue,
            ):
                failure_parts.append(chunk)

            failure_text = ensure_failure_next_action_footer(
                "".join(failure_parts),
                user_request=user_request,
                payload=failure_payload,
            )
            for frame in adapter.emit_design_summary(failure_text):
                yield frame

            adapter.mark_explanation_sent()

        yield from adapter.finalize(final_state, compiler_mode=compiler_mode)
        self._record_generation_turn(session_id, user_request, final_state, result)

    @staticmethod
    def _generation_turn_summary(
        state: AgentState,
        result: dict,
        *,
        user_request: str = "",
    ) -> str:
        from copilot.next_action import ensure_build_next_action_footer

        workflow = result.get("workflow") if isinstance(result.get("workflow"), dict) else None
        if workflow:
            name = workflow.get("name") or workflow.get("workflow_id") or "Workflow"
            node_count = len(workflow.get("nodes") or [])
            body = f"Built **{name}** ({node_count} nodes) on the canvas."
            return ensure_build_next_action_footer(
                body,
                workflow=workflow,
                user_request=user_request,
            )
        if state.is_valid:
            return "Updated the workflow on the canvas."
        error_msg = result.get("error") or state.runtime_smoke_error
        if error_msg:
            return f"Could not complete the workflow change: {error_msg}"
        if state.errors:
            return f"Could not complete the workflow change: {state.errors[0].get('message', 'validation failed')}"
        return "Workflow generation finished."

    def _record_generation_turn(
        self,
        session_id: str | None,
        user_request: str,
        state: AgentState,
        result: dict,
    ) -> None:
        if not session_id:
            return
        self.record_thread_turn(
            session_id,
            user_message=user_request,
            assistant_message=self._generation_turn_summary(
                state, result, user_request=user_request
            ),
        )

    def _result_from_state(self, state: AgentState, *, compiler_mode: str) -> dict:
        healing = list(state.auto_fixes_applied)
        healing.extend(state.canonicalization_applied)
        valid = state.is_valid

        if not valid:
            error_msg = state.runtime_smoke_error
            if not error_msg and state.errors:
                error_msg = state.errors[0].get("message", "Generation failed")
            return {
                "success": False,
                "error": error_msg or "Generation failed",
                "history": [],
                "attempts": state.attempts,
                "validation": state.validation,
                "healing_steps": healing,
                "compiler_mode": "harness",
                "compiler_mode_requested": compiler_mode,
                "workflow": None,
            }

        return {
            "success": True,
            "workflow": state.workflow,
            "history": [],
            "attempts": state.attempts,
            "validation": state.validation,
            "healing_steps": healing,
            "compiler_mode": "harness",
            "compiler_mode_requested": compiler_mode,
        }

    def explain_run_stream(
        self,
        workflow: dict[str, Any],
        run_log: list[dict[str, Any]],
        run_result: dict[str, Any] | None = None,
        run_error: str | None = None,
        user_message: str | None = None,
        suggested_sql: str | None = None,
        route_metadata: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream a post-run execution summary for the Copilot chat panel."""
        from copilot.thinking_monologue import ThinkingMonologueContext
        from .thinking_sse import yield_llm_thinking_monologue

        ctx = ThinkingMonologueContext.for_explain_run(
            user_message or "",
            workflow,
            run_log,
            route_metadata=route_metadata,
        )
        monologue = ""
        for frame in yield_llm_thinking_monologue(ctx):
            monologue = str(frame.get("detail") or monologue)
            yield frame

        parts: list[str] = []

        def _emit(piece: str) -> None:
            parts.append(piece)

        text = stream_run_execution_summary(
            workflow,
            run_log,
            run_result,
            _emit,
            run_error=run_error,
            user_message=user_message,
            suggested_sql=suggested_sql,
            route_metadata=route_metadata,
            planning_monologue=monologue,
        )
        yield {"type": "text_start"}
        import time
        for chunk in _chunk_run_text(text):
            yield {"type": "text_chunk", "chunk": chunk}
            time.sleep(0.015)
        yield {"type": "text_end"}
        yield {"type": "done", "success": True, "compiler_mode": "harness"}


def _chunk_run_text(text: str, size: int = 48) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


def _state_from_complete_event(
    event: Any,
    *,
    scenario: str,
    max_attempts: int,
) -> AgentState:
    validation = event.data.get("validation") or {}
    return AgentState(
        scenario=scenario,
        max_attempts=max_attempts,
        attempts=int(event.data.get("attempts") or 0),
        max_steps=int(event.data.get("max_steps") or 0),
        step_count=int(event.data.get("step_count") or 0),
        step_budget_hit=bool(event.data.get("step_budget_hit") or False),
        workflow=event.data.get("workflow") or event.data.get("draft_workflow"),
        validation=validation,
        errors=list(validation.get("errors") or []),
        warnings=list(validation.get("warnings") or []),
        auto_fixes_applied=list(event.data.get("auto_fixes_applied") or []),
        canonicalization_applied=list(event.data.get("canonicalization_applied") or []),
        runtime_smoke_passed=event.data.get("runtime_smoke_passed"),
        runtime_smoke_error=event.data.get("runtime_smoke_error"),
        planning_monologue=str(event.data.get("planning_monologue") or ""),
    )
