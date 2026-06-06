"""Shared SSE frames for Sherpa 'Thought for Ns' thinking blocks."""
from __future__ import annotations

from typing import Any, Iterator


def thinking_monologue_frame(*, stage_id: str = "thinking-1") -> dict[str, Any]:
    return {
        "type": "agent_stage",
        "stage_id": stage_id,
        "stage": "Thinking",
        "subagent_name": "Thinking",
        "subagent_type": "thinking",
        "thinking_monologue": True,
    }


def yield_thinking_monologue(monologue: str, *, stage_id: str = "thinking-1") -> Iterator[dict[str, Any]]:
    """Emit running + done agent_stage frames for a first-person planning monologue."""
    text = (monologue or "").strip()
    base = thinking_monologue_frame(stage_id=stage_id)
    yield {
        **base,
        "status": "running",
        "detail": text,
        "outcome": text,
    }
    yield {
        **base,
        "status": "done",
        "detail": text,
        "outcome": text,
    }


def yield_llm_thinking_monologue(
    ctx: Any,
    *,
    stage_id: str = "thinking-1",
    adapter: Any | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream LLM thinking monologue frames with growing detail for the UI typewriter."""
    from copilot.thinking_monologue import iter_thinking_monologue_updates

    base = thinking_monologue_frame(stage_id=stage_id)
    monologue = ""
    for monologue in iter_thinking_monologue_updates(ctx, adapter=adapter):
        yield {
            **base,
            "status": "running",
            "detail": monologue,
            "outcome": monologue,
        }
    if not (monologue or "").strip():
        return
    yield {
        **base,
        "status": "done",
        "detail": monologue,
        "outcome": monologue,
    }
