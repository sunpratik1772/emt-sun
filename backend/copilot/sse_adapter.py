"""Map orchestrator pipeline events → Copilot UI SSE (thinking / text / workflow_created)."""
from __future__ import annotations

from typing import Any, Iterator

# User-facing step labels — never surface raw validator dumps in the UI.
_STAGE_LABELS: dict[str, str] = {
    "pipeline-start": "Drafting workflow…",
    "plan": "Asking Gemini…",
    "extract": "Parsing response…",
    "validate-schema": "Checking node schema…",
    "validate-semantic": "Running dry simulation…",
    "repair": "Self-healing workflow…",
    "validated": "Workflow validated",
    "exhausted": "Applying best-effort workflow…",
}

_WARNING_LABELS: dict[str, str] = {
    "validate-schema": "Fixing schema issues…",
    "validate-semantic": "Adjusting data flow…",
    "extract": "Retrying after parse error…",
    "exhausted": "Repair attempts exhausted",
}


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


class OrchestratorSseAdapter:
    """Stateful converter from `run_pipeline_sync` emit() events to UI SSE frames."""

    def __init__(self) -> None:
        self._text_started = False
        self._workflow_sent = False
        self._pending_workflow: dict | None = None

    def convert(self, ev: dict[str, Any]) -> list[dict[str, Any]]:
        etype = ev.get("type")
        out: list[dict[str, Any]] = []

        if etype == "thinking":
            step = str(ev.get("step", "")).strip()
            if step:
                out.append({"type": "thinking", "step": step[:200]})
            return out

        if etype == "status":
            stage = str(ev.get("stage", ""))
            label = _STAGE_LABELS.get(stage) or str(ev.get("message", stage))[:120]
            if stage == "repair":
                attempt = ev.get("attempt")
                if attempt:
                    label = f"Self-healing (attempt {attempt})…"
            out.append({"type": "thinking", "step": label})
            return out

        if etype == "warning":
            stage = str(ev.get("stage", ""))
            label = _WARNING_LABELS.get(stage, "Refining workflow…")
            out.append({"type": "thinking", "step": label})
            return out

        if etype == "workflow":
            wf = ev.get("workflow")
            if isinstance(wf, dict):
                self._pending_workflow = wf
                out.extend(self._workflow_created_events(wf))
            return out

        if etype == "message":
            content = str(ev.get("content", "")).strip()
            if content:
                out.extend(self._text_events(content))
            return out

        if etype == "complete":
            wf = ev.get("workflow") or self._pending_workflow
            if isinstance(wf, dict) and not self._workflow_sent:
                out.extend(self._workflow_created_events(wf))
            if not self._text_started:
                answer = str(ev.get("answer") or ev.get("message") or "").strip()
                if answer:
                    out.extend(self._text_events(answer))
            out.append({"type": "done"})
            return out

        if etype == "error":
            msg = str(ev.get("message", "Generation failed"))
            out.append({"type": "error", "message": msg[:500]})
            return out

        return out

    def _workflow_created_events(self, wf: dict) -> list[dict[str, Any]]:
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

    def _text_events(self, content: str) -> list[dict[str, Any]]:
        frames: list[dict[str, Any]] = []
        if not self._text_started:
            self._text_started = True
            frames.append({"type": "text_start"})
        for chunk in _chunk_text(content):
            frames.append({"type": "text_chunk", "chunk": chunk})
        frames.append({"type": "text_end"})
        return frames

    def finalize(
        self,
        result: dict[str, Any],
        *,
        compiler_mode: str = "orchestrator",
    ) -> Iterator[dict[str, Any]]:
        """Emit terminal frames after the pipeline returns (best-effort / missing workflow)."""
        wf = result.get("workflow")
        if isinstance(wf, dict) and not self._workflow_sent:
            yield from self.convert({"type": "workflow", "workflow": wf})

        if not self._text_started:
            answer = (result.get("answer") or "").strip()
            if answer:
                for frame in self._text_events(answer):
                    yield frame
            elif result.get("error") and not wf:
                yield {"type": "error", "message": str(result["error"])[:500]}
                return

        if result.get("success") is False and wf and not self._text_started:
            err = (result.get("error") or "Workflow has validation issues").strip()
            for frame in self._text_events(err):
                yield frame

        yield {
            "type": "done",
            "success": bool(result.get("success") or wf),
            "compiler_mode": compiler_mode,
        }
