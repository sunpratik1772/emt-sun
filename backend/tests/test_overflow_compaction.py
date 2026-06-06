from __future__ import annotations

from generation.harness.compactor import CompactionInput, compact_history, render_compacted_summary
from generation.harness.overflow_guard import compute_overflow


def test_overflow_detects_large_payload() -> None:
    text = "x" * 400000
    decision = compute_overflow(text, model_hint="default", reserved_tokens=2000)
    assert decision.overflow is True
    assert decision.estimated_tokens > decision.usable_tokens


def test_compaction_preserves_recent_tail() -> None:
    history = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
    summary, recent = compact_history(history, preserve_tail_messages=3)
    assert "Critical Context" in summary
    assert len(recent) == 3
    assert recent[0]["content"] == "msg 7"


def test_compaction_template_sections_present() -> None:
    text = render_compacted_summary(
        CompactionInput(
            goal="Ship migration",
            constraints=["No regressions"],
            done=["Phase 1 complete"],
            in_progress=["Phase 2"],
            blocked=[],
            decisions=["Use deterministic checks"],
            next_steps=["Add tests"],
            critical_context=["runner.py changed"],
            relevant_files=["backend/agent/harness/runner.py"],
        )
    )
    for section in (
        "## Goal",
        "## Constraints & Preferences",
        "## Progress",
        "## Key Decisions",
        "## Next Steps",
        "## Critical Context",
        "## Relevant Files",
    ):
        assert section in text
