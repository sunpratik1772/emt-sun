"""
AgentRunner — the control system around the Planner.

Responsibilities (per the blueprint):
  * control retries
  * track state
  * apply constraints
  * measure quality
  * prevent bad outputs

Flow for a single run:

    1. Emit `understanding` + `planning` events (so the UI timeline has
       the familiar shape).
    2. Call Planner with the initial prompt.
    3. Parse → Validate.
    4. If valid: emit success, return.
    5. If invalid: run AutoFixer. If it clears all errors, emit an
       `auto_fixing` event and return without consuming an LLM attempt.
    6. If still invalid: build repair brief → Planner → repeat up to
       `max_attempts` times.

The runner yields `AgentEvent`s. The HTTP adapter translates those to
SSE frames. The blocking caller just drains the iterator and inspects
the final state.
"""
from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any, Iterator

from engine.dag_runner import run_workflow
from engine.mcp_nodes import is_mcp_node_type, workflow_uses_mcp
from engine.node_availability import is_agent_visible_type
from llm import GeminiAdapter, gemini_configured, get_default_adapter

logger = logging.getLogger(__name__)

from ..planner import Planner
from ..prompt_builder import PromptBuilder
from ..canonicalizer import Canonicalizer
from ..repair.auto_fixer import AutoFixer
from ..validator_adapter import ValidatorAdapter
from copilot.build_narration import build_contextual_plan_steps
from copilot.workflow_finalize import finalize_workflow

from .enrichment import (
    build_generation_context,
    intent_summary_detail,
    known_datasets,
    retrieve_summary_parts,
)
from .blueprint_router import BlueprintDecision
from .agent_profiles import resolve_max_steps, resolve_primary_profile
from .compactor import compact_history
from .memory import MemoryManager
from .metrics import AgentMetrics, get_metrics
from .overflow_guard import compute_overflow
from .output_truncation import truncate_with_spillover
from .retriever import ContextRetriever
from .state import AgentEvent, AgentPhase, AgentState
from .task_manager import TaskManager, TaskRecord

_SMOKE_ALERT_PAYLOAD = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "alert_date": "2024-01-15",
    "currency_pair": "EUR/USD",
    "alert_id": "SMOKE-001",
}
_SMOKE_SAMPLE_LIST_LIMIT = 2
def _default_parallel_llm_subagents() -> str:
    """Enable LLM planning bullets when Gemini is configured unless explicitly disabled."""
    try:
        from llm import gemini_configured

        return "1" if gemini_configured() else "0"
    except Exception:
        return "0"


_SMOKE_WALL_CLOCK_S = max(15, int(os.environ.get("HARNESS_SMOKE_TIMEOUT_S", "90") or "90"))
_SMOKE_MCP_HTTP_TIMEOUT_S = max(5.0, float(os.environ.get("HARNESS_SMOKE_MCP_TIMEOUT_S", "20") or "20"))
def _integration_node_types() -> frozenset[str]:
    from engine.registry import all_specs

    active = {s.type_id for s in all_specs()}
    base = {"github", "slack", "gmail", "notion", "telegram"}
    return frozenset(active | base | {"mcp"})


_INTEGRATION_NODE_TYPES = _integration_node_types()
_INTEGRATION_ERROR_TERMS = (
    "404",
    "401",
    "403",
    "400",
    "500",
    "502",
    "503",
    "504",
    "not found",
    "unauthorized",
    "forbidden",
    "credentials",
    "credential",
    "token",
    "auth",
    "connect",
    "timeout",
    "timed out",
    "dns",
    "refused",
    "name resolution",
    "servname",
    "mcp",
    "jira",
    "confluence",
    "github",
    "atlassian",
    "mcp_bridge",
    "bridge_error",
    "placeholder",
    "{{",
    "unresolved",
    "issue type",
    "project key",
    "space key",
    "api error",
    "http error",
)


def _workflow_has_integration_nodes(workflow: dict | None) -> bool:
    if not workflow:
        return False
    for node in workflow.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        ntype = str(node.get("type") or "").lower()
        if is_mcp_node_type(ntype) or ntype in _INTEGRATION_NODE_TYPES:
            return True
    return False


def _is_integration_smoke_error(message: str, workflow: dict | None = None) -> bool:
    """True when failure is creds/MCP/placeholder — not a repairable DAG defect."""
    lower = (message or "").lower()
    if not lower:
        return False
    if any(term in lower for term in _INTEGRATION_ERROR_TERMS):
        return True
    if _workflow_has_integration_nodes(workflow):
        if any(term in lower for term in ("failed", "error", "exception", "invalid", "rejected")):
            return True
    return False


def _execute_smoke_workflow(workflow: dict) -> None:
    """Run smoke DAG with bounded wall-clock time and shorter MCP HTTP timeout."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    prev_mcp_timeout = os.environ.get("MCP_HTTP_TIMEOUT")
    os.environ["MCP_HTTP_TIMEOUT"] = str(_SMOKE_MCP_HTTP_TIMEOUT_S)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_workflow, workflow, _SMOKE_ALERT_PAYLOAD)
            future.result(timeout=_SMOKE_WALL_CLOCK_S)
    except FuturesTimeout as exc:
        raise TimeoutError(
            f"Runtime smoke timed out after {_SMOKE_WALL_CLOCK_S}s"
        ) from exc
    finally:
        if prev_mcp_timeout is None:
            os.environ.pop("MCP_HTTP_TIMEOUT", None)
        else:
            os.environ["MCP_HTTP_TIMEOUT"] = prev_mcp_timeout
class AgentRunner:
    def __init__(
        self,
        planner: Planner | None = None,
        prompt_builder: PromptBuilder | None = None,
        validator: ValidatorAdapter | None = None,
        auto_fixer: AutoFixer | None = None,
        canonicalizer: Canonicalizer | None = None,
        metrics: AgentMetrics | None = None,
        memory: MemoryManager | None = None,
        retriever: ContextRetriever | None = None,
        task_manager: TaskManager | None = None,
        parallel_llm_adapter: GeminiAdapter | None = None,
    ) -> None:
        self.planner = planner or Planner()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.validator = validator or ValidatorAdapter()
        self.auto_fixer = auto_fixer or AutoFixer()
        self.canonicalizer = canonicalizer or Canonicalizer(auto_fixer=self.auto_fixer)
        self.metrics = metrics or get_metrics()
        self.memory = memory or MemoryManager()
        self.retriever = retriever or ContextRetriever(memory=self.memory)
        self.task_manager = task_manager or TaskManager(executor=self._default_task_executor)
        self.parallel_enabled = os.environ.get("HARNESS_ENABLE_PARALLEL_TASKS", "1").lower() in {
            "1", "true", "yes", "on"
        }
        self.parallel_max_tasks = max(1, int(os.environ.get("HARNESS_PARALLEL_MAX_TASKS", "4") or "4"))
        self.task_timeout_ms = max(100, int(os.environ.get("HARNESS_TASK_TIMEOUT_MS", "15000") or "15000"))
        self.parallel_llm_subagents = os.environ.get(
            "HARNESS_PARALLEL_LLM_SUBAGENTS",
            _default_parallel_llm_subagents(),
        ).lower() in {
            "1", "true", "yes", "on"
        }
        self.parallel_llm_model = (os.environ.get("HARNESS_PARALLEL_LLM_MODEL") or "").strip() or None
        self.parallel_llm_max_tokens = max(
            128, int(os.environ.get("HARNESS_PARALLEL_LLM_MAX_OUTPUT_TOKENS", "512") or "512")
        )
        self._parallel_llm_adapter = parallel_llm_adapter or get_default_adapter()
        self.truncation_dir = Path(__file__).resolve().parents[3] / "output" / "harness_truncation"
        self.runtime_smoke_enabled = os.environ.get("DBSHERPA_RUNTIME_SMOKE", "1").lower() in {
            "1", "true", "yes", "on"
        }

    # --------------------------------------------------------------------
    # Public API — both shapes delegate to _run() which does the real work.
    # --------------------------------------------------------------------
    def run(
        self,
        scenario: str,
        max_attempts: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
        thread_context: str | None = None,
    ) -> AgentState:
        """Blocking entry-point. Drains the stream and returns final state."""
        state: AgentState | None = None
        for ev, s in self._run(
            scenario,
            max_attempts,
            current_workflow,
            recent_errors,
            selected_node_id,
            thread_context,
        ):
            state = s  # last yielded state is the final one
        assert state is not None  # _run always yields at least once
        return state

    def stream(
        self,
        scenario: str,
        max_attempts: int = 3,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
        thread_context: str | None = None,
    ) -> Iterator[AgentEvent]:
        """Streaming entry-point. Yields AgentEvents as the run progresses."""
        for ev, _state in self._run(
            scenario,
            max_attempts,
            current_workflow,
            recent_errors,
            selected_node_id,
            thread_context,
        ):
            yield ev

    # --------------------------------------------------------------------
    # Inner driver — yields (event, state) so both API shapes can read
    # whatever they need without duplicating logic.
    # --------------------------------------------------------------------
    def _run(
        self,
        scenario: str,
        max_attempts: int,
        current_workflow: dict | None = None,
        recent_errors: list[dict] | None = None,
        selected_node_id: str | None = None,
        thread_context: str | None = None,
    ) -> Iterator[tuple[AgentEvent, AgentState]]:
        self.metrics.record_run_start()
        state = AgentState(scenario=scenario, max_attempts=max_attempts)
        state.profile = resolve_primary_profile(scenario)
        state.max_steps = resolve_max_steps(state.profile)
        self.memory.observe_turn(scenario)
        history: list[dict] = []
        editing_mode = current_workflow is not None
        if editing_mode and not self._is_tool_allowed(state, "edit"):
            yield from self._emit_permission_denied(state, "edit", mandatory=True)
            return

        # ── Phase: understanding (intent classification) ------------------
        yield AgentEvent(
            AgentPhase.UNDERSTANDING, "Understanding the request",
            detail=(
                f"Editing existing workflow · {scenario[:100]}"
                if editing_mode
                else f"Parsing: {scenario[:120]}"
            ),
        ), state

        gen_ctx = build_generation_context(
            scenario,
            current_workflow=current_workflow,
            known_datasets=known_datasets(),
            known_node_types=self.prompt_builder._known_node_types(),
            retriever=self.retriever,
        )
        intent = gen_ctx.intent
        retrieved = gen_ctx.retrieved
        blueprint = gen_ctx.blueprint

        summary_detail = intent_summary_detail(
            intent,
            editing_mode=editing_mode,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            scenario=scenario,
        )
        yield AgentEvent(
            AgentPhase.UNDERSTANDING, "Understanding the request",
            status="done",
            detail=summary_detail,
            data={"intent": intent.to_dict()},
        ), state

        # ── Phase: retrieving (context, templates, memory) ----------------
        yield AgentEvent(
            AgentPhase.RETRIEVING, "Retrieving context",
            detail="Loading skills, templates, memory, and schemas",
        ), state

        state.matched_skills = retrieved.matched_skills
        if retrieved.template_name:
            state.template_id = retrieved.template_name

        all_skills = self.prompt_builder.list_skills()
        retrieve_detail_parts = retrieve_summary_parts(retrieved, len(all_skills))

        yield AgentEvent(
            AgentPhase.RETRIEVING, "Retrieving context",
            status="done",
            detail=" · ".join(retrieve_detail_parts),
            data={
                "skills": all_skills,
                "matched": retrieved.matched_skills,
                "template": retrieved.template_name,
                "example_count": len(retrieved.example_workflows),
                "has_memory": bool(retrieved.memory_text),
                "blueprint_id": blueprint.blueprint_id if blueprint else None,
            },
        ), state

        if blueprint is not None:
            yield AgentEvent(
                AgentPhase.PLANNING,
                "matched_blueprint",
                status="done",
                detail="",
                data={"blueprint_id": blueprint.blueprint_id, "blueprint_title": blueprint.title},
            ), state

        from copilot.thinking_monologue import ThinkingMonologueContext, iter_thinking_monologue_updates

        ctx = ThinkingMonologueContext.for_build(
            scenario,
            intent,
            blueprint,
            current_workflow=current_workflow,
        )
        monologue = ""
        for monologue in iter_thinking_monologue_updates(ctx):
            state.planning_monologue = monologue
            yield AgentEvent(
                AgentPhase.PLANNING,
                "Thinking",
                detail=monologue,
                data={
                    "subagent_name": "Thinking",
                    "subagent_type": "thinking",
                    "thinking_monologue": True,
                },
            ), state
        yield AgentEvent(
            AgentPhase.PLANNING,
            "Thinking",
            status="done",
            detail=monologue,
            data={
                "subagent_name": "Thinking",
                "subagent_type": "thinking",
                "thinking_monologue": True,
                "outcome": monologue,
            },
        ), state

        system_prompt = self.prompt_builder.system_prompt(
            scenario=scenario,
            current_workflow=current_workflow,
        )
        matched = retrieved.matched_skills
        parallel_context = ""
        if self.parallel_enabled and not self._should_skip_parallel_planning(intent, blueprint):
            yield AgentEvent(
                AgentPhase.PLANNING,
                "dispatch_parallel_tasks",
                detail="Planning parallel-safe task units",
            ), state
            task_ids = self._dispatch_parallel_tasks(
                state,
                scenario,
                intent=intent,
                blueprint=blueprint,
                planning_monologue=state.planning_monologue,
            )
            for task_id in task_ids:
                try:
                    task = self.task_manager.get_task(task_id)
                except Exception:
                    continue
                yield AgentEvent(
                    AgentPhase.PLANNING,
                    "parallel_subagent",
                    detail=task.description,
                    data={
                        "task_id": task.task_id,
                        "subagent_name": task.description,
                        "subagent_type": task.subagent_type,
                    },
                ), state
            results = self._collect_parallel_results(task_ids)
            for result in results:
                yield AgentEvent(
                    AgentPhase.PLANNING,
                    "parallel_subagent",
                    status="done",
                    detail=result.get("description", ""),
                    data={
                        "task_id": result.get("task_id"),
                        "subagent_name": result.get("description"),
                        "subagent_type": result.get("subagent_type"),
                        "outcome": result.get("result_text") or result.get("error") or "",
                    },
                ), state
            for result in results:
                if result.get("result_text"):
                    self.memory.note_task_output(result["result_text"])
            parallel_context = self._render_parallel_context(results)
            if task_ids:
                snippets = [
                    str(r.get("result_text") or r.get("error") or "").strip()[:120]
                    for r in results
                    if isinstance(r, dict)
                ]
                snippets = [s for s in snippets if s]
                yield AgentEvent(
                    AgentPhase.PLANNING,
                    "collect_parallel_results",
                    status="done",
                    detail=f"Merged {len(results)} planning note(s) into the draft prompt",
                    data={
                        "parallel_results": results,
                        "outcome": " · ".join(snippets[:3]) if snippets else "",
                    },
                ), state
        # ── Phase: initial generation -------------------------------------
        yield AgentEvent(
            AgentPhase.GENERATING, "Creating nodes & edges",
            detail="Calling LLM for initial workflow draft",
        ), state

        initial_turn = self.prompt_builder.initial_prompt(
            scenario,
            current_workflow=current_workflow,
            recent_errors=recent_errors,
            selected_node_id=selected_node_id,
            matched_skills=matched,
            thread_context=thread_context,
            planning_monologue=state.planning_monologue,
        ) + gen_ctx.enrichment_suffix + parallel_context
        if not self._consume_step_budget(state):
            yield from self._handle_step_budget_exhausted(state)
            return
        if state.step_count >= state.max_steps:
            initial_turn += self.prompt_builder.last_step_snippet()
        try:
            system_prompt, history, initial_turn = self._prepare_for_llm(
                system_prompt, history, initial_turn, state
            )
            plan = self.planner.generate(system_prompt, history, initial_turn)
        except Exception as exc:
            yield AgentEvent(
                AgentPhase.ERROR, "Generation failed", status="error", detail=str(exc),
            ), state
            self.metrics.record_run_failure(attempts=0, error_codes=["LLM_CALL_FAILED"])
            return

        history.append({"role": "user", "content": initial_turn})
        history.append({"role": "assistant", "content": plan.raw})
        state.raw_text = self._truncate_large_output(plan.raw)
        state.workflow = plan.workflow
        can = self.canonicalizer.canonicalize(state.workflow)
        if can.workflow is not None:
            state.workflow = can.workflow
        if can.changed:
            state.canonicalization_passes += 1
            state.canonicalization_applied.extend(can.applied)

        state.validation = self.validator.validate(state.workflow)
        if editing_mode and state.workflow is not None:
            from copilot.improvement_acceptance import (
                align_improvement_requirements_with_canvas,
                apply_improvement_acceptance,
                infer_requirements_from_scenario,
            )

            reqs = infer_requirements_from_scenario(scenario, editing_mode=True)
            reqs = align_improvement_requirements_with_canvas(current_workflow, reqs)
            state.validation = apply_improvement_acceptance(
                state.workflow,
                state.validation,
                reqs,
            )
        state.errors = state.validation.get("errors", [])
        state.warnings = state.validation.get("warnings", [])

        if state.workflow is not None:
            yield AgentEvent(
                AgentPhase.GENERATING, "Creating nodes & edges", status="done",
                detail="Workflow structure is ready.",
                data={"draft_summary": _summarize(state.workflow)},
            ), state
        else:
            yield AgentEvent(
                AgentPhase.GENERATING, "Creating nodes & edges", status="error",
                detail="Draft was not parseable JSON",
            ), state

        if state.is_valid:
            smoke_ok = yield from self._run_runtime_smoke(state)
            if smoke_ok:
                yield from self._emit_success(state)
                return

        # ── Phase: deterministic auto-fix pass (no LLM) -------------------
        # We only try auto-fix when we have *something* to patch. If the
        # LLM returned unparseable JSON there's nothing to mechanically fix.
        if state.workflow is not None:
            yield from self._try_auto_fix(state)
            if state.is_valid:
                smoke_ok = yield from self._run_runtime_smoke(state)
                if smoke_ok:
                    yield from self._emit_success(state)
                    return

        # ── Phase: LLM repair loop ----------------------------------------
        while state.attempts < state.max_attempts:
            if not self._consume_step_budget(state):
                yield from self._handle_step_budget_exhausted(state)
                return
            attempt = state.attempts + 1
            current_errors = state.errors
            repair_msg = self.prompt_builder.repair_prompt(
                current_errors,
                attempt,
                state.max_attempts,
                planning_monologue=state.planning_monologue,
            )
            if state.step_count >= state.max_steps:
                repair_msg += self.prompt_builder.last_step_snippet()

            yield AgentEvent(
                AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                detail=(
                    f"{len(current_errors)} validator error(s) to fix"
                    if state.workflow is not None
                    else "Re-asking for parseable JSON"
                ),
                data={
                    "attempt": attempt,
                    "validation_errors": current_errors[:12],
                },
            ), state

            try:
                system_prompt, history, repair_msg = self._prepare_for_llm(
                    system_prompt, history, repair_msg, state
                )
                plan = self.planner.generate(system_prompt, history, repair_msg)
            except Exception as exc:
                yield AgentEvent(
                    AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                    status="error", detail=str(exc),
                    data={"attempt": attempt},
                ), state
                yield AgentEvent(
                    AgentPhase.ERROR, "Repair failed", status="error", detail=str(exc),
                ), state
                self.metrics.record_run_failure(
                    attempts=attempt,
                    error_codes=[e.get("code", "ERROR") for e in current_errors],
                )
                return

            history.append({"role": "user", "content": repair_msg})
            history.append({"role": "assistant", "content": plan.raw})
            state.raw_text = self._truncate_large_output(plan.raw)
            state.attempts = attempt

            if plan.workflow is None:
                # Don't clobber the previous best draft. Let the loop retry.
                yield AgentEvent(
                    AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                    status="error", detail="Repair output was not valid JSON",
                    data={"attempt": attempt},
                ), state
                continue

            state.workflow = plan.workflow
            can = self.canonicalizer.canonicalize(state.workflow)
            if can.workflow is not None:
                state.workflow = can.workflow
            if can.changed:
                state.canonicalization_passes += 1
                state.canonicalization_applied.extend(can.applied)
            state.validation = self.validator.validate(state.workflow)
            state.errors = state.validation.get("errors", [])
            state.warnings = state.validation.get("warnings", [])

            approved = state.is_valid
            yield AgentEvent(
                AgentPhase.CRITIQUING, f"Repair pass {attempt}/{state.max_attempts}",
                status="done",
                detail=(
                    "APPROVED — validator clean" if approved
                    else f"{len(state.errors)} error(s) remain"
                ),
                data={
                    "attempt": attempt,
                    "approved": approved,
                    "summary": _summarize(state.workflow),
                    "validation_errors": state.errors[:12],
                },
            ), state

            if approved:
                smoke_ok = yield from self._run_runtime_smoke(state)
                if smoke_ok:
                    yield from self._emit_success(state)
                    return

            # Try an auto-fix pass after each LLM repair — the model
            # often fixes 90% of errors and leaves a hard-rule holdout
            # that AutoFixer can patch without burning another attempt.
            yield from self._try_auto_fix(state)
            if state.is_valid:
                smoke_ok = yield from self._run_runtime_smoke(state)
                if smoke_ok:
                    yield from self._emit_success(state)
                    return

        # ── Exhausted attempts --------------------------------------------
        yield AgentEvent(
            AgentPhase.FINALIZING, "Finalizing workflow", status="done",
            detail=(
                f"{len(state.workflow.get('nodes', []))} nodes · "
                f"{len(state.workflow.get('edges', []))} edges · "
                f"{len(state.errors)} unresolved error(s)"
                if state.workflow is not None
                else "No parseable workflow after all attempts"
            ),
        ), state
        yield AgentEvent(
            AgentPhase.COMPLETE, "Workflow ready" if state.is_valid else "Workflow failed",
            status="done" if state.is_valid else "error",
            detail=state.workflow.get("name", "") if state.workflow else "",
            data={
                # Guardrail guarantee: never hand the UI a workflow that the
                # deterministic validator rejected. The failed draft stays in
                # validation/raw diagnostics, but it must not be loaded or saved.
                "workflow": state.workflow if state.is_valid else None,
                "draft_workflow": state.workflow,
                "validation": state.validation,
                "attempts": state.attempts,
                "auto_fixes_applied": state.auto_fixes_applied,
                "canonicalization_changed": bool(state.canonicalization_applied),
                "canonicalization_applied": state.canonicalization_applied,
                "runtime_smoke_passed": state.runtime_smoke_passed,
                "runtime_smoke_error": state.runtime_smoke_error,
                "profile": state.profile.name if state.profile else None,
                "max_steps": state.max_steps,
                "step_count": state.step_count,
                "step_budget_hit": state.step_budget_hit,
            },
        ), state
        self.metrics.record_run_failure(
            attempts=state.attempts,
            error_codes=[e.get("code", "ERROR") for e in state.errors],
        )
        self._record_outcome(state)
        self.memory.compact()

    # --------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------
    def _is_tool_allowed(self, state: AgentState, tool_name: str) -> bool:
        if state.profile is None:
            return True
        return bool(state.profile.permissions.get(tool_name, False))

    def _emit_permission_denied(
        self, state: AgentState, tool_name: str, *, mandatory: bool
    ) -> Iterator[tuple[AgentEvent, AgentState]]:
        detail = f"Permission denied for tool '{tool_name}' under profile '{state.profile.name if state.profile else 'unknown'}'."
        yield AgentEvent(
            AgentPhase.ERROR,
            "Permission denied",
            status="error",
            detail=detail,
            data={"error_code": "PERMISSION_DENIED", "tool": tool_name},
        ), state
        if mandatory:
            yield AgentEvent(
                AgentPhase.COMPLETE,
                "Workflow failed",
                status="error",
                detail="",
                data={
                    "workflow": None,
                    "validation": state.validation,
                    "attempts": state.attempts,
                    "auto_fixes_applied": state.auto_fixes_applied,
                    "canonicalization_changed": bool(state.canonicalization_applied),
                    "canonicalization_applied": state.canonicalization_applied,
                    "runtime_smoke_passed": state.runtime_smoke_passed,
                    "runtime_smoke_error": state.runtime_smoke_error,
                    "profile": state.profile.name if state.profile else None,
                    "max_steps": state.max_steps,
                    "step_count": state.step_count,
                    "step_budget_hit": state.step_budget_hit,
                    "error_code": "PERMISSION_DENIED",
                },
            ), state
            self.metrics.record_run_failure(
                attempts=state.attempts,
                error_codes=["PERMISSION_DENIED"],
            )
            self.memory.compact()

    def _default_task_executor(self, task: TaskRecord) -> tuple[str, dict]:
        llm_result = self._run_parallel_llm_task(task)
        heuristic_summary, heuristic_payload = self._heuristic_parallel_summary(task)
        if llm_result and not self._looks_truncated_parallel_output(llm_result):
            return (
                llm_result,
                {
                    "task_id": task.task_id,
                    "subagent_type": task.subagent_type,
                    "description": task.description,
                    "execution_mode": "llm",
                },
            )
        if llm_result and self._looks_truncated_parallel_output(llm_result):
            merged = f"{llm_result.strip()}\n{heuristic_summary}"
            return (
                merged,
                {
                    "task_id": task.task_id,
                    "subagent_type": task.subagent_type,
                    "description": task.description,
                    "execution_mode": "llm+heuristic",
                },
            )

        return heuristic_summary, heuristic_payload

    def _heuristic_parallel_summary(self, task: TaskRecord) -> tuple[str, dict]:
        text = task.prompt.lower()
        desc_lower = (task.description or "").lower()
        if "market_ticks" in text or "market_ticks" in desc_lower or "spread" in desc_lower:
            summary = (
                "Use db_query on market_ticks; filter or branch when spread_pips exceeds the threshold; "
                "shape alert rows before publishing."
            )
        elif "confluence" in text and "jira" in text:
            summary = (
                "Plan MCP sequence: publish Confluence digest rows, then create Jira issues "
                "with mapped summary/description fields."
            )
        elif "confluence" in text:
            summary = "Shape confluence_publish_report title/body/space from upstream alert rows."
        elif "jira" in text:
            summary = "Map alert rows to jira_create_issue with valid project key and summary fields."
        elif "condition" in text or "threshold" in text or "branch" in text:
            summary = "Use condition true/false branches so alert-side effects only run on trigger rows."
        elif "db_query" in text or "dataset" in text or "schema" in desc_lower:
            summary = (
                "Use db_query on the named sources and validate required columns before transforms. "
                "Keep only contract-backed fields in downstream nodes."
            )
        elif "validation" in text or "validation" in desc_lower or "evaluator" in text:
            summary = (
                "Add an evaluator node to validate required fields (forwards passed rows only; sets _eval, not _passed). "
                "Summarize with Starlark code or map_transform, then branch before Confluence publish."
            )
        elif is_agent_visible_type("outlook") and (
            "outlook" in text or "outlook" in desc_lower or "email" in text
        ):
            summary = (
                "Add an Outlook node on the success branch with summary rows from the final dataset. "
                "Configure OUTLOOK_* credentials in backend/.env before live send."
            )
        elif "confluence" in desc_lower and "summary" in text:
            summary = (
                "Publish a Confluence summary page from the final workflow rows using the MCP publish tool "
                "with title, body, and space mapped from upstream output."
            )
        elif "join" in text:
            summary = "Validate join keys and preserve both-source fields before post-join filtering."
        else:
            summary = f"Planned: {task.description}"
        return (
            summary,
            {
                "task_id": task.task_id,
                "subagent_type": task.subagent_type,
                "description": task.description,
                "execution_mode": "heuristic",
            },
        )

    def _looks_truncated_parallel_output(self, text: str) -> bool:
        t = (text or "").strip()
        if len(t) < 24:
            return True
        tail = t[-1]
        if tail in ".!?)]\"'`":
            return False
        if t.endswith((" for", " and", " with", " to", " the", " a", " an")):
            return True
        return tail in ",;:"

    def _run_parallel_llm_task(self, task: TaskRecord) -> str:
        if not self.parallel_llm_subagents:
            return ""
        if not gemini_configured():
            return ""
        sys_prompt = (
            "You are a focused Sherpa parallel subagent. Return concise planning guidance only. "
            "Use 3-5 bullet lines in plain text. Each bullet must be a complete sentence ending "
            "with a period. No markdown fences, no section headers, no trailing fragments."
        )
        user_prompt = (
            f"Subtask: {task.description}\n"
            f"Type: {task.subagent_type}\n"
            f"Instruction: {task.prompt}\n\n"
            "Produce:\n"
            "1) key constraints\n"
            "2) recommended node/tool sequence\n"
            "3) likely failure traps and mitigations"
        )
        try:
            text = self._parallel_llm_adapter.single_shot(
                user_prompt,
                model=self.parallel_llm_model,
                temperature=0.1,
                max_output_tokens=self.parallel_llm_max_tokens,
                system_prompt=sys_prompt,
            )
            return (text or "").strip()
        except Exception:
            return ""

    def _should_skip_parallel_planning(self, intent, blueprint) -> bool:
        """Skip noisy parallel planning for simple linear load→transform→export builds."""
        if blueprint is not None and getattr(blueprint, "parallel_tasks", None):
            return False
        scenarios = list(getattr(intent, "scenarios", None) or [])
        if scenarios:
            return False
        datasets = list(getattr(intent, "datasets", None) or [])
        artifacts = set(getattr(intent, "artifacts", None) or [])
        simple_artifacts = {"csv", "excel", "email", "file", "xlsx"}
        if len(datasets) <= 1 and (not artifacts or artifacts.issubset(simple_artifacts)):
            return True
        return False

    def _dispatch_parallel_tasks(
        self,
        state: AgentState,
        scenario: str,
        *,
        intent,
        blueprint: BlueprintDecision | None,
        planning_monologue: str = "",
    ) -> list[str]:
        if not self._is_tool_allowed(state, "task"):
            return []
        plan_prefix = ""
        if (planning_monologue or "").strip():
            plan_prefix = (
                "Sherpa planning (binding — align your output with this):\n"
                f"{planning_monologue.strip()}\n\n"
            )
        clauses: list[tuple[str, str, str]] = []
        if blueprint is not None and blueprint.parallel_tasks:
            clauses = [
                (t.subagent_type, t.description, t.prompt)
                for t in blueprint.parallel_tasks[: self.parallel_max_tasks]
            ]
        else:
            # Build "parallel-safe" clauses from intent signals instead of raw "and" splits.
            intent_clauses: list[tuple[str, str, str]] = []
            if intent.datasets:
                ds = ", ".join(intent.datasets[:4])
                intent_clauses.append(
                    (
                        "explore",
                        "Checking data sources",
                        f"Confirm which columns from {ds} are needed for this workflow.",
                    )
                )
            if intent.actions:
                acts = ", ".join(intent.actions[:4])
                intent_clauses.append(
                    (
                        "general",
                        "Designing workflow steps",
                        f"Outline the steps needed to {acts}.",
                    )
                )
            if intent.artifacts:
                artifacts = ", ".join(intent.artifacts[:4])
                intent_clauses.append(
                    (
                        "general",
                        "Planning export",
                        f"Plan how to produce the {artifacts} output at the end.",
                    )
                )
            clauses = intent_clauses[: self.parallel_max_tasks]
        if len(clauses) < 2:
            return []
        task_ids: list[str] = []
        for subagent_type, description, prompt in clauses[: self.parallel_max_tasks]:
            task = self.task_manager.create_task(
                subagent_type=subagent_type,
                description=description[:120],
                prompt=plan_prefix + prompt,
                background=True,
            )
            task_ids.append(task.task_id)
        return task_ids

    def _collect_parallel_results(self, task_ids: list[str]) -> list[dict]:
        results: list[dict] = []
        for task_id in task_ids:
            task = self.task_manager.await_task(task_id, timeout_ms=self.task_timeout_ms)
            results.append(
                {
                    "task_id": task.task_id,
                    "status": task.status,
                    "subagent_type": task.subagent_type,
                    "description": task.description,
                    "result_text": task.result_text,
                    "error": task.error,
                }
            )
        return results

    def _render_parallel_context(self, results: list[dict]) -> str:
        if not results:
            return ""
        lines = ["\n\n<parallel_task_results>"]
        for r in results:
            status = r.get("status")
            desc = r.get("description")
            if status == "completed":
                lines.append(f"- {desc}: {r.get('result_text')}")
            else:
                lines.append(f"- {desc}: status={status} error={r.get('error')}")
        lines.append("</parallel_task_results>")
        return "\n".join(lines)

    def _prepare_for_llm(
        self,
        system_prompt: str,
        history: list[dict],
        user_turn: str,
        state: AgentState,
    ) -> tuple[str, list[dict], str]:
        bundle = system_prompt + "\n" + user_turn + "\n" + "\n".join(
            str(h.get("content", "")) for h in history
        )
        decision = compute_overflow(bundle, model_hint=state.profile.model_hint if state.profile else "default")
        self.memory.note_token_stats(decision.estimated_tokens, decision.usable_tokens)
        if not decision.overflow:
            return system_prompt, history, user_turn

        summary, new_history = compact_history(history, preserve_tail_messages=4)
        if summary:
            system_prompt = system_prompt + "\n\n<compacted_context>\n" + summary + "\n</compacted_context>"
        self.memory.observe_edit_pattern("Context compaction run due to overflow.")
        return system_prompt, new_history, user_turn

    def _truncate_large_output(self, raw_text: str) -> str:
        max_lines = int(os.environ.get("HARNESS_TRUNCATE_MAX_LINES", "120") or "120")
        max_bytes = int(os.environ.get("HARNESS_TRUNCATE_MAX_BYTES", "16000") or "16000")
        result = truncate_with_spillover(
            raw_text,
            output_dir=self.truncation_dir,
            max_lines=max_lines,
            max_bytes=max_bytes,
        )
        return result.preview

    def _try_auto_fix(self, state: AgentState) -> Iterator[tuple[AgentEvent, AgentState]]:
        """Apply deterministic fixes and re-validate.

        We work on a deep copy first so a buggy rule can't corrupt the
        state; only swap the workflow in if the repaired version has
        strictly fewer errors.
        """
        if state.workflow is None:
            return
        if not self._is_tool_allowed(state, "edit"):
            yield from self._emit_permission_denied(state, "edit", mandatory=False)
            return
        candidate = copy.deepcopy(state.workflow)
        report = self.auto_fixer.fix(candidate, state.errors)
        if not report.changed:
            return

        new_validation = self.validator.validate(candidate)
        new_errors = new_validation.get("errors", [])

        # Only accept the rewrite if it's a strict improvement. AutoFixer
        # is supposed to be safe, but "don't make things worse" is a
        # cheap invariant to enforce at the harness level.
        if len(new_errors) >= len(state.errors):
            return

        state.workflow = candidate
        state.validation = new_validation
        state.errors = new_errors
        state.warnings = new_validation.get("warnings", [])
        state.auto_fix_passes += 1
        state.auto_fixes_applied.extend(report.applied)
        self.metrics.record_auto_fix(report.applied)

        yield AgentEvent(
            AgentPhase.AUTO_FIXING, "Deterministic auto-fix",
            status="done",
            detail=(
                f"Applied {len(report.applied)} mechanical fix(es); "
                + (
                    "validator clean"
                    if new_validation["valid"]
                    else f"{len(new_errors)} error(s) remain"
                )
            ),
            data={
                "applied": report.applied,
                "approved": new_validation["valid"],
                "summary": _summarize(candidate),
            },
        ), state

    def _record_outcome(self, state: AgentState) -> None:
        """Buffer memory observations about this run's outcome."""
        node_count = len(state.workflow.get("nodes", [])) if state.workflow else 0
        self.memory.observe_workflow_result(
            workflow_name=state.scenario[:60],
            node_count=node_count,
            success=state.is_valid,
            errors=state.errors if not state.is_valid else None,
        )
        if state.auto_fixes_applied:
            self.memory.observe_edit_pattern(
                f"Auto-fixes applied: {', '.join(state.auto_fixes_applied[:5])}"
            )

    def _emit_success(self, state: AgentState) -> Iterator[tuple[AgentEvent, AgentState]]:
        if state.workflow is not None:
            state.workflow = finalize_workflow(state.workflow)
        yield AgentEvent(
            AgentPhase.FINALIZING, "Finalizing workflow", status="done",
            detail=(
                f"{len(state.workflow.get('nodes', []))} nodes · "
                f"{len(state.workflow.get('edges', []))} edges"
            ),
        ), state
        yield AgentEvent(
            AgentPhase.COMPLETE, "Workflow ready", status="done",
            detail=state.workflow.get("name", "") if state.workflow else "",
            data={
                "workflow": state.workflow,
                "validation": state.validation,
                "attempts": state.attempts,
                "auto_fixes_applied": state.auto_fixes_applied,
                "canonicalization_changed": bool(state.canonicalization_applied),
                "canonicalization_applied": state.canonicalization_applied,
                "runtime_smoke_passed": state.runtime_smoke_passed,
                "runtime_smoke_error": state.runtime_smoke_error,
                "profile": state.profile.name if state.profile else None,
                "max_steps": state.max_steps,
                "step_count": state.step_count,
                "step_budget_hit": state.step_budget_hit,
                "planning_monologue": state.planning_monologue,
            },
        ), state
        self.metrics.record_run_success(attempts=state.attempts)
        self._record_outcome(state)
        self.memory.compact()

    def _consume_step_budget(self, state: AgentState) -> bool:
        if state.max_steps <= 0:
            return True
        if state.step_count >= state.max_steps:
            state.step_budget_hit = True
            return False
        state.step_count += 1
        if state.step_count >= state.max_steps:
            state.step_budget_hit = True
        return True

    def _handle_step_budget_exhausted(
        self, state: AgentState
    ) -> Iterator[tuple[AgentEvent, AgentState]]:
        # If we already have a valid draft we can still complete safely.
        if state.is_valid and state.workflow is not None:
            yield from self._emit_success(state)
            return

        detail = (
            f"Step budget exhausted at {state.step_count}/{state.max_steps}. "
            "No valid workflow available."
        )
        yield AgentEvent(
            AgentPhase.ERROR,
            "Step budget exhausted",
            status="error",
            detail=detail,
        ), state
        yield AgentEvent(
            AgentPhase.COMPLETE,
            "Workflow failed",
            status="error",
            detail="",
            data={
                "workflow": None,
                "validation": state.validation,
                "attempts": state.attempts,
                "auto_fixes_applied": state.auto_fixes_applied,
                "canonicalization_changed": bool(state.canonicalization_applied),
                "canonicalization_applied": state.canonicalization_applied,
                "runtime_smoke_passed": state.runtime_smoke_passed,
                "runtime_smoke_error": state.runtime_smoke_error,
                "profile": state.profile.name if state.profile else None,
                "max_steps": state.max_steps,
                "step_count": state.step_count,
                "step_budget_hit": state.step_budget_hit,
            },
        ), state
        self.metrics.record_run_failure(
            attempts=state.attempts,
            error_codes=[e.get("code", "ERROR") for e in state.errors] or ["STEP_BUDGET_EXHAUSTED"],
        )
        self._record_outcome(state)
        self.memory.compact()

    def _run_runtime_smoke(self, state: AgentState) -> Iterator[tuple[AgentEvent, AgentState]]:
        if not self.runtime_smoke_enabled:
            state.runtime_smoke_passed = None
            state.runtime_smoke_error = None
            return True
        if state.workflow is None or not state.is_valid:
            return False

        yield AgentEvent(
            AgentPhase.FINALIZING,
            "Runtime smoke test",
            detail="Executing reduced-sample workflow for runtime validity",
        ), state

        # Avoid re-running full MCP smoke on every LLM repair pass — that caused
        # multi-minute "erroneous runs" when env/creds were missing.
        if (
            state.attempts > 0
            and state.smoke_integration_bypassed
            and _workflow_has_integration_nodes(state.workflow)
        ):
            state.runtime_smoke_passed = True
            state.runtime_smoke_error = None
            yield AgentEvent(
                AgentPhase.FINALIZING,
                "Runtime smoke test",
                status="done",
                detail="Skipped repeat smoke (integration environment already accepted)",
                data={"runtime_smoke_passed": True, "skipped_repeat": True},
            ), state
            return True

        candidate = _prepare_smoke_workflow(state.workflow)
        try:
            _execute_smoke_workflow(candidate)
        except Exception as exc:
            message = str(exc)

            if _is_integration_smoke_error(message, state.workflow):
                logger.info("Runtime smoke bypassed integration/env error: %s", message[:240])
                state.runtime_smoke_passed = True
                state.runtime_smoke_error = message[:500]
                state.smoke_integration_bypassed = True
                yield AgentEvent(
                    AgentPhase.FINALIZING,
                    "Runtime smoke test",
                    status="done",
                    detail=f"Structure OK — integration/env not live: {message[:160]}",
                    data={"runtime_smoke_passed": True, "bypassed_error": message},
                ), state
                return True

            state.runtime_smoke_passed = False
            state.runtime_smoke_error = message
            self._inject_runtime_smoke_failure(state, message)
            yield AgentEvent(
                AgentPhase.FINALIZING,
                "Runtime smoke test",
                status="error",
                detail=message,
                data={"runtime_smoke_passed": False, "runtime_smoke_error": message},
            ), state
            return False

        state.runtime_smoke_passed = True
        state.runtime_smoke_error = None
        state.smoke_integration_bypassed = False
        yield AgentEvent(
            AgentPhase.FINALIZING,
            "Runtime smoke test",
            status="done",
            detail="Reduced-sample execution passed",
            data={"runtime_smoke_passed": True},
        ), state
        return True

    def _inject_runtime_smoke_failure(self, state: AgentState, message: str) -> None:
        base = copy.deepcopy(state.validation or {})
        warnings = list(base.get("warnings") or [])
        existing_errors = [
            err for err in (base.get("errors") or [])
            if err.get("code") != "RUNTIME_SMOKE_FAILED"
        ]
        existing_errors.append(
            {
                "code": "RUNTIME_SMOKE_FAILED",
                "message": f"Runtime smoke test failed: {message}",
                "severity": "error",
                "node_id": None,
                "field": None,
            }
        )
        state.validation = {
            "valid": False,
            "errors": existing_errors,
            "warnings": warnings,
            "summary": f"{len(existing_errors)} error(s), {len(warnings)} warning(s)",
        }
        state.errors = existing_errors
        state.warnings = warnings


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _prepare_smoke_workflow(workflow: dict) -> dict:
    candidate = copy.deepcopy(workflow)
    for node in candidate.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if node.get("type") != "MANUAL_TRIGGER":
            continue
        cfg = node.get("config")
        if not isinstance(cfg, dict):
            continue
        emitted_items = cfg.get("emitted_items")
        if isinstance(emitted_items, list):
            cfg["emitted_items"] = _truncate_sample_value(emitted_items)
            node["config"] = cfg
    return candidate


def _truncate_sample_value(value: object, depth: int = 0) -> object:
    if depth >= 6:
        return value
    if isinstance(value, list):
        return [_truncate_sample_value(v, depth + 1) for v in value[:_SMOKE_SAMPLE_LIST_LIMIT]]
    if isinstance(value, dict):
        return {k: _truncate_sample_value(v, depth + 1) for k, v in value.items()}
    return value


def _summarize(wf: dict) -> dict:
    return {
        "name": wf.get("name"),
        "node_count": len(wf.get("nodes", [])),
        "edge_count": len(wf.get("edges", [])),
        "node_types": sorted(
            {n.get("type") for n in wf.get("nodes", []) if n.get("type")}
        ),
    }
