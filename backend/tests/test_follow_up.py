"""Tests for multi-turn follow-up repair."""
from __future__ import annotations

from copilot.follow_up import (
    action_follow_up_build_override,
    action_follow_up_outlook_unavailable_override,
    action_follow_up_run_override,
    enrich_route_metadata_for_follow_up,
    looks_like_action_acceptance,
    repair_follow_up_text,
)
from copilot.next_action import is_sample_run_next_step
from copilot.llm_router import finalize_sherpa_route, SherpaRoute


def test_repair_coomss_typo_to_comms_messages() -> None:
    text = repair_follow_up_text("add 20 coomss and highlight email ones")
    assert "comms_messages" in text
    assert "coomss" not in text.lower()


def test_enrich_metadata_sets_edit_and_workflow_name() -> None:
    meta = enrich_route_metadata_for_follow_up(
        {},
        message="add filter",
        canvas_workflow={"name": "High-risk leads export", "nodes": [{"config": {"source": "leads.csv"}}]},
    )
    assert meta.get("edit_existing_workflow") is True
    assert meta.get("workflow_name") == "High-risk leads export"
    assert "leads.csv" in (meta.get("session_datasets") or [])


def test_finalize_sherpa_route_repairs_follow_up() -> None:
    route = SherpaRoute(
        intent="build",
        reason="edit",
        enhanced_question="add 20 coomss",
        metadata={"edit_existing_workflow": True},
        source="llm",
    )
    out = finalize_sherpa_route(
        route,
        message="add 20 coomss and highlight email ones",
        canvas_workflow={"name": "Leads export", "nodes": [{"config": {"source": "leads.csv"}}]},
    )
    assert "comms_messages" in out.enhanced_question


def test_yes_after_sample_run_offer_wants_run_not_build() -> None:
    thread = (
        "User: extract comms and export csv\n"
        "Sherpa: Built **Extract and Filter Comms Messages by Keyword**.\n\n"
        "**Next step:** Run **Extract and Filter Comms Messages by Keyword** "
        "with sample data to preview the export.\n\n"
        "Want me to start a sample run now?"
    )
    wf = {"name": "Extract and Filter Comms Messages by Keyword", "nodes": []}
    assert is_sample_run_next_step(
        "Run **Extract and Filter Comms Messages by Keyword** with sample data to preview the export",
        "Want me to start a sample run now",
    )
    assert action_follow_up_build_override("yes", thread_context=thread, canvas_workflow=wf) is None
    run_ov = action_follow_up_run_override("yes", thread_context=thread, canvas_workflow=wf)
    assert run_ov is not None
    assert run_ov["metadata"]["wants_sample_run"] is True
    assert run_ov["metadata"].get("edit_existing_workflow") is False

    out = finalize_sherpa_route(
        SherpaRoute(intent="build", reason="rebuild", enhanced_question="yes", metadata={}, source="llm"),
        message="yes",
        thread_context=thread,
        canvas_workflow=wf,
    )
    assert out.metadata.get("wants_sample_run") is True
    assert out.intent == "ask"


def test_yes_after_adjust_step_offer_routes_to_build_not_run() -> None:
    thread = (
        "Sherpa: Empty run.\n\n"
        "**Next step:** Loosen the filter on **Validate Report Content** in **GitHub Activity Briefing Report**.\n\n"
        "Want me to apply that change on the canvas?"
    )
    wf = {
        "name": "GitHub Activity Briefing Report",
        "nodes": [{"id": "n01", "type": "manual_trigger"}],
    }
    assert action_follow_up_run_override("yes", thread_context=thread, canvas_workflow=wf) is None
    build_ov = action_follow_up_build_override("yes", thread_context=thread, canvas_workflow=wf)
    assert build_ov is not None
    assert build_ov["intent"] == "build"
    assert build_ov["metadata"]["edit_existing_workflow"] is True
    assert "Loosen" in build_ov["enhanced_question"]


def test_outlook_unavailable_routes_to_remove_outlook_nodes() -> None:
    wf = {
        "name": "GitHub Activity Briefing Report",
        "nodes": [{"id": "n01", "type": "github"}],
    }
    ov = action_follow_up_outlook_unavailable_override(
        "outlook node not available",
        canvas_workflow=wf,
    )
    assert ov is not None
    assert ov["intent"] == "build"
    assert "remove" in ov["enhanced_question"].lower()
    assert ov["metadata"].get("wants_outlook") is False


def test_do_it_routes_to_build_after_join_suggestion() -> None:
    thread = (
        'Review the latest run of "Join Comms Messages with HS Alerts and Rank".\n'
        "Reliability Improvement Suggestion: Node n04 was configured as a left join "
        "but executed as an inner join. Ensure the join operation consistently executes as a left join."
    )
    assert looks_like_action_acceptance("do it")
    override = action_follow_up_build_override(
        "do it",
        thread_context=thread,
        canvas_workflow={"name": "Join Comms Messages with HS Alerts and Rank", "nodes": []},
    )
    assert override is not None
    assert override["intent"] == "build"
    assert override["metadata"]["edit_existing_workflow"] is True
    assert "left" in override["enhanced_question"].lower()
    assert "Join Comms Messages with HS Alerts and Rank" in override["enhanced_question"]

    out = finalize_sherpa_route(
        SherpaRoute(
            intent="explain_run",
            reason="still about reliability",
            enhanced_question="review reliability again",
            metadata={"run_selector": "latest"},
            source="llm",
        ),
        message="do it",
        thread_context=thread,
        canvas_workflow={"name": "Join Comms Messages with HS Alerts and Rank", "nodes": []},
    )
    assert out.intent == "build"
    assert out.metadata.get("edit_existing_workflow") is True
    assert "left" in out.enhanced_question.lower()


def test_yes_after_truncated_build_summary_still_routes_to_run() -> None:
    """Long build replies were truncated at 900 chars, dropping the Next step footer."""
    long_body = "x" * 1200
    assistant = (
        f"{long_body}\n\n**Next step:** Run **Trade and Communications Summary** "
        "with sample data to preview the export.\n\nWant me to start a sample run now?"
    )
    from copilot.thread_context import format_thread_context

    thread = format_thread_context([{"role": "assistant", "content": assistant}])
    wf = {"name": "Trade and Communications Summary", "nodes": [{"id": "n01"}]}
    run_ov = action_follow_up_run_override("yes", thread_context=thread, canvas_workflow=wf)
    assert run_ov is not None
    assert run_ov["metadata"]["wants_sample_run"] is True

    out = finalize_sherpa_route(
        SherpaRoute(intent="build", reason="rebuild", enhanced_question="yes", metadata={}, source="llm"),
        message="yes",
        thread_context=thread,
        canvas_workflow=wf,
    )
    assert out.intent == "ask"
    assert out.metadata.get("wants_sample_run") is True
    assert out.metadata.get("edit_existing_workflow") is False

