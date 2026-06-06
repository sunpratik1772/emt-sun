"""Thinking monologue polish — strip template slop from LLM text."""
from __future__ import annotations

from copilot.thinking_monologue import (
    _is_unacceptable_monologue,
    _polish_thinking_monologue,
)


def test_polish_strips_user_wants_and_step_count_filler() -> None:
    raw = (
        "User wants load hs_trades.\n"
        "2-step pipeline should work.\n"
        "Drafting now."
    )
    out = _polish_thinking_monologue(raw)
    assert "user wants" not in out.lower()
    assert "pipeline should work" not in out.lower()
    assert _is_unacceptable_monologue(out)


def test_polish_user_wants_export_is_rejected_not_shipped() -> None:
    raw = "User wants export.\n2-step pipeline should work.\nDrafting now."
    out = _polish_thinking_monologue(raw)
    assert _is_unacceptable_monologue(out)
