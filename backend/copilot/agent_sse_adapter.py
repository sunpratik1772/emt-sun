"""Map AgentRunner phase events → Copilot UI SSE frames."""
from __future__ import annotations

from typing import Any, Iterator

from generation.harness.state import AgentEvent, AgentPhase, AgentState

from .progress_narration import progress_description, stage_title

# Labels for high-level harness phases. Sub-phases (repair pass, smoke test)
# keep their event.label instead of collapsing into these buckets.
_PHASE_LABELS: dict[AgentPhase, str] = {
    AgentPhase.UNDERSTANDING: "Reading request",
    AgentPhase.RETRIEVING: "Reading context",
    AgentPhase.PLANNING: "Planning in parallel",
    AgentPhase.GENERATING: "Drafting workflow",
    AgentPhase.AUTO_FIXING: "Applying fixes",
    AgentPhase.CRITIQUING: "Repairing workflow",
    AgentPhase.FINALIZING: "Validating workflow",
    AgentPhase.ERROR: "Generation error",
    AgentPhase.COMPLETE: "Workflow generated",
}

def _clip(text: str, limit: int = 1200) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _canonical_stage(event: AgentEvent) -> str:
    return (event.label or "").strip() or _PHASE_LABELS.get(event.phase, event.phase.value)


def _chunk_text(text: str, size: int = 48) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size
    return chunks


class AgentSseAdapter:
    """Stateful converter from AgentEvent streams to Studio SSE frames."""

    def __init__(self, user_request: str = "") -> None:
        self.user_request = user_request
        self._workflow_sent = False
        self._text_started = False
        self._explanation_sent = False
        self._open_phases: set[str] = set()
        self._stage_seq = 0
        self._phase_stage_ids: dict[str, str] = {}
        
        # Parse prompt for intelligent keywords
        self.db_name = self._parse_db(user_request)
        self.service_name = self._parse_service(user_request)
        self.var_name = self._parse_var(user_request)

    def _parse_db(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if "postgres" in p:
            return "Postgres"
        if "sqlite" in p:
            return "SQLite"
        if "mysql" in p:
            return "MySQL"
        if "solr" in p:
            return "Solr"
        if "clickhouse" in p:
            return "ClickHouse"
        if "db" in p or "database" in p:
            return "Database"
        return "Database"

    def _parse_service(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if "todo-api" in p or "todo api" in p:
            return "todo-api"
        if "hono" in p:
            return "Hono API"
        if "slack" in p:
            return "Slack service"
        if "jira" in p:
            return "Jira service"
        if "confluence" in p:
            return "Confluence service"
        if "github" in p:
            return "GitHub service"
        if "teams" in p:
            return "Teams service"
        if "outlook" in p:
            return "Outlook service"
        if "email" in p or "mail" in p:
            return "Email service"
        if "telegram" in p:
            return "Telegram service"
        return "App Service"

    def _parse_var(self, prompt: str) -> str:
        p = (prompt or "").lower()
        if "database_url" in p or "database-url" in p or "postgres" in p:
            return "DATABASE_URL"
        if "github_token" in p or "github-token" in p or "github" in p:
            return "GITHUB_TOKEN"
        if "atlassian" in p or "jira" in p or "confluence" in p:
            return "ATLASSIAN_API_TOKEN"
        if "slack" in p:
            return "SLACK_WEBHOOK_URL"
        return "ENVIRONMENT_VARIABLES"

    def convert(self, event: AgentEvent) -> list[dict[str, Any]]:
        if event.phase == AgentPhase.COMPLETE:
            return []

        subagent_type = event.data.get("subagent_type")
        subagent_name = event.data.get("subagent_name")
        contextual = bool(event.data.get("contextual_plan"))
        thinking = bool(event.data.get("thinking_monologue"))
        if thinking:
            label = "Thinking"
        elif contextual:
            label = str(event.label or subagent_name or "Planning").strip()
        else:
            label = stage_title(event, db_name=self.db_name)
        progress = progress_description(event)
        harness_detail = (event.detail or "").strip()

        if event.status == "running":
            self._open_phases.add(event.phase.value)
            stage_id = self._open_stage_id(event, label)
            if thinking:
                detail = harness_detail or progress
            elif not subagent_type:
                detail = ""
            else:
                detail = harness_detail or progress
            frame = self._agent_stage_frame(
                event,
                stage_id=stage_id,
                label=label,
                status="running",
                detail=detail,
                outcome=detail,
            )
            return [frame]

        if event.status == "done":
            frames = []
            if event.phase.value in self._open_phases:
                self._open_phases.discard(event.phase.value)
            stage_id = self._close_stage_id(event, label)
            outcome = progress if contextual else progress
            if contextual and event.data.get("outcome"):
                outcome = str(event.data.get("outcome"))
            if event.data.get("thinking_monologue"):
                detail = harness_detail or outcome
                outcome = detail
            elif contextual:
                detail = harness_detail or outcome
            else:
                detail = ""
                outcome = ""
            frame = self._agent_stage_frame(
                event,
                stage_id=stage_id,
                label=label,
                status="done",
                detail=detail,
                outcome=outcome,
            )
            frames.append(frame)
            return frames

        if event.status == "error":
            msg = event.detail or event.label or "Generation failed"
            
            # Analyze error with Gemini to explain reasoning and fix strategy
            explanation = ""
            try:
                from llm import gemini_configured, get_default_adapter
                if gemini_configured():
                    adapter = get_default_adapter()
                    sys_prompt = (
                        "You are dbSherpa Copilot. Explain the workflow run/compilation error concisely in 2 sentences: "
                        "1) why it failed (reasoning) and 2) what should be fixed/changed in the next attempt."
                    )
                    user_prompt = f"User Request: {self.user_request}\nError: {msg}"
                    explanation = adapter.single_shot(
                        user_prompt,
                        system_prompt=sys_prompt,
                        temperature=0.2,
                        max_output_tokens=180,
                    )
            except Exception:
                pass

            if explanation:
                outcome_text = f"{msg}\n\n[Analysis]\n{explanation.strip()}"
            else:
                outcome_text = msg

            frames = []
            stage_id = self._close_stage_id(event, label)
            frames.append(
                {
                    "type": "agent_stage",
                    "stage_id": stage_id,
                    "stage": label,
                    "status": "error",
                    "detail": msg,
                    "outcome": outcome_text,
                    "subagent_name": subagent_name,
                    "subagent_type": subagent_type,
                }
            )
            return frames

        return []

    def emit_design_summary(self, text: str) -> Iterator[dict[str, Any]]:
        yield from self._text_events(text)

    def mark_explanation_sent(self) -> None:
        self._explanation_sent = True

    def finalize(
        self,
        state: AgentState,
        *,
        compiler_mode: str = "harness",
    ) -> Iterator[dict[str, Any]]:
        if state.is_valid and isinstance(state.workflow, dict) and not self._workflow_sent:
            yield from self._workflow_created_events(state.workflow)

        if not state.is_valid and not self._workflow_sent and not self._explanation_sent:
            messages = [
                str(e.get("message") or "").strip()
                for e in (state.errors or [])
                if isinstance(e, dict) and e.get("message")
            ]
            if state.runtime_smoke_error:
                messages.append(str(state.runtime_smoke_error))
            err = messages[0] if messages else "Workflow generation failed"
            if len(messages) > 1:
                err = f"{err} (+{len(messages) - 1} more)"
            yield {"type": "error", "message": err[:500]}

        yield {
            "type": "done",
            "success": bool(state.is_valid),
            "compiler_mode": compiler_mode,
        }

    def _workflow_created_events(self, wf: dict[str, Any]) -> list[dict[str, Any]]:
        if self._workflow_sent:
            return []
        self._workflow_sent = True
        nodes = wf.get("nodes") or []
        return [{
            "type": "workflow_created",
            "workflowId": wf.get("workflow_id") or wf.get("id") or "draft",
            "name": wf.get("name") or "Untitled workflow",
            "nodeCount": len(nodes),
            "workflow": wf,
        }]

    def _next_stage_id(self, event: AgentEvent, label: str) -> str:
        self._stage_seq += 1
        norm = (label or event.phase.value).lower().replace(" ", "_")
        return f"{norm}-{self._stage_seq}"

    def _stage_key(self, event: AgentEvent) -> str:
        data = event.data or {}
        if data.get("thinking_monologue"):
            return "thinking-monologue"
        if data.get("contextual_plan") and event.label:
            return f"ctx-{event.label}"
        if "task_id" in data:
            return f"task-{data['task_id']}"
        return event.phase.value

    def _open_stage_id(self, event: AgentEvent, label: str) -> str:
        stage_id = self._next_stage_id(event, label)
        self._phase_stage_ids[self._stage_key(event)] = stage_id
        return stage_id

    def _close_stage_id(self, event: AgentEvent, label: str) -> str:
        return self._phase_stage_ids.pop(self._stage_key(event), self._next_stage_id(event, label))

    def _agent_stage_frame(
        self,
        event: AgentEvent,
        *,
        stage_id: str,
        label: str,
        status: str,
        detail: str,
        outcome: str,
    ) -> dict[str, Any]:
        data = event.data or {}
        frame: dict[str, Any] = {
            "type": "agent_stage",
            "stage_id": stage_id,
            "stage": label,
            "status": status,
            "detail": detail,
            "outcome": outcome,
            "subagent_name": data.get("subagent_name"),
            "subagent_type": data.get("subagent_type"),
        }
        if data.get("contextual_plan"):
            frame["contextual_plan"] = True
            if data.get("prompt_anchor"):
                frame["prompt_anchor"] = data.get("prompt_anchor")
        if data.get("thinking_monologue"):
            frame["thinking_monologue"] = True
        return frame

    def _text_events(self, content: str) -> list[dict[str, Any]]:
        import time
        frames: list[dict[str, Any]] = []
        if not self._text_started:
            self._text_started = True
            frames.append({"type": "text_start"})
        for chunk in _chunk_text(content):
            frames.append({"type": "text_chunk", "chunk": chunk})
            time.sleep(0.015)
        frames.append({"type": "text_end"})
        return frames

    def emit_text_chunk(self, chunk: str) -> Iterator[dict[str, Any]]:
        if not self._text_started:
            self._text_started = True
            yield {"type": "text_start"}
        yield {"type": "text_chunk", "chunk": chunk}

    def emit_text_end(self) -> Iterator[dict[str, Any]]:
        yield {"type": "text_end"}
