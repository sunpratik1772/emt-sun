"""Shared thinking monologue SSE frames."""
from __future__ import annotations

from copilot.thinking_sse import yield_thinking_monologue


def test_yield_thinking_monologue_emits_running_and_done() -> None:
    frames = list(yield_thinking_monologue("User wants load data.\nDrafting now."))
    assert len(frames) == 2
    assert frames[0]["status"] == "running"
    assert frames[1]["status"] == "done"
    assert frames[0]["thinking_monologue"] is True
    assert frames[0]["subagent_type"] == "thinking"
    assert "load data" in frames[0]["detail"]
