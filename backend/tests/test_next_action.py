"""Tests for Sherpa next-step closers and follow-up parsing."""
from __future__ import annotations

from copilot.follow_up import action_follow_up_build_override, extract_build_action_from_thread
from copilot.next_action import (
    ensure_build_next_action_footer,
    ensure_next_action_footer,
    format_next_action_block,
    infer_build_next_action,
    infer_run_review_next_action,
    is_canvas_edit_next_step,
    is_sample_run_next_step,
    parse_next_action_from_text,
    pending_action_from_thread,
)


def test_parse_next_action_without_bold_markers() -> None:
    text = (
        "Built workflow.\n\n"
        "Next step: Run **Demo** with sample data to preview the export.\n\n"
        "Want me to start a sample run now?"
    )
    action, question = parse_next_action_from_text(text)
    assert action is not None
    assert "sample data" in action.lower()
    assert question is not None
    assert is_sample_run_next_step(action, question)


def test_parse_next_action_block() -> None:
    text = (
        "Some analysis here.\n\n"
        "**Next step:** Update the join node so it executes as a left join.\n\n"
        "Want me to apply that fix on the canvas?"
    )
    action, question = parse_next_action_from_text(text)
    assert action is not None
    assert "left join" in action.lower()
    assert question is not None
    assert "apply" in question.lower()


def test_pending_action_from_thread() -> None:
    thread = (
        "User: Review the latest run.\n"
        "Sherpa: Summary…\n\n"
        "**Next step:** Update **Join Comms and Alerts** so joinType left runs as a left join.\n\n"
        "Want me to apply that fix on the canvas?"
    )
    pending = pending_action_from_thread(thread)
    assert pending is not None
    assert "left join" in pending.lower()


def test_do_it_uses_next_step_block() -> None:
    thread = (
        "User: suggest one change\n"
        "Sherpa: …\n\n"
        "**Next step:** Fix the join node to use a left join.\n\n"
        "Want me to apply that on the canvas?"
    )
    action = extract_build_action_from_thread(
        thread,
        canvas_workflow={"name": "Join Comms Messages with HS Alerts and Rank", "nodes": []},
    )
    assert action is not None
    assert "Fix the join node" in action
    override = action_follow_up_build_override(
        "do it",
        thread_context=thread,
        canvas_workflow={"name": "Join Comms Messages with HS Alerts and Rank", "nodes": []},
    )
    assert override is not None
    assert override["intent"] == "build"
    assert "Fix the join node" in override["enhanced_question"]


def test_ensure_next_action_appends_when_missing() -> None:
    wf = {"name": "Join workflow", "nodes": [{"type": "join", "label": "Join A and B"}]}
    verification = {"verification_summary": {"join_type_mismatch": True}}
    out = ensure_next_action_footer("Run completed.", workflow=wf, verification=verification)
    assert "**Next step:**" in out
    assert "left join" in out.lower()


def test_format_next_action_block() -> None:
    block = format_next_action_block("Update the filter threshold", "Want me to change it on the canvas")
    assert block.startswith("**Next step:**")
    assert block.endswith("?")


def test_is_sample_run_next_step() -> None:
    assert is_sample_run_next_step(
        "Run **Orders export** with sample data to preview the export",
        "Want me to start a sample run now",
    )
    assert not is_sample_run_next_step(
        "Update the join node so it executes as a left join",
        "Want me to apply that fix on the canvas",
    )
    assert not is_sample_run_next_step(
        "Re-run **GitHub Activity Briefing Report** with sample data to confirm the output",
        "Want me to help you adjust a step first",
    )
    assert is_canvas_edit_next_step(
        "Re-run **GitHub Activity Briefing Report** with sample data to confirm the output",
        "Want me to help you adjust a step first",
    )


def test_infer_build_next_action_export_prompt() -> None:
    block = infer_build_next_action(
        {"name": "Excel Report: Orders Top Contributors"},
        user_request="Create an Excel report from orders.csv with sorted top contributors.",
    )
    assert block is not None
    assert "sample run" in block.lower()
    assert block.endswith("?")


def test_ensure_build_next_action_appends_when_missing() -> None:
    wf = {"name": "Orders export"}
    out = ensure_build_next_action_footer(
        "**Orders export**\n\n`orders.csv` → `output.xlsx`",
        workflow=wf,
        user_request="export orders to excel",
    )
    assert "**Next step:**" in out
    assert "?" in out.split("**Next step:**")[-1]


def test_infer_run_review_next_action_join_mismatch() -> None:
    block = infer_run_review_next_action(
        {"name": "W", "nodes": [{"type": "join", "label": "Join X"}]},
        {"verification_summary": {"join_type_mismatch": True}},
        user_message="suggest one change",
    )
    assert block is not None
    assert "Join X" in block
