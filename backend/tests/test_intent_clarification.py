"""Tests for Sherpa intent clarification layer."""
from __future__ import annotations

from copilot.intent_clarification import (
    SherpaClarification,
    assess_route_clarification,
    resolve_clarification_selection,
)
from copilot.llm_router import SherpaRoute


def test_sample_run_affirmation_skips_confirm() -> None:
    """Yes after sample-run offer should run like /run, not open Questions panel."""
    thread = (
        "User: build comms summary\n"
        "Sherpa: Built **Comms Messages High-Risk Summary** (4 nodes).\n\n"
        "**Next step:** Run **Comms Messages High-Risk Summary** with sample data.\n\n"
        "Want me to start a sample run now?"
    )
    route = SherpaRoute(
        intent="ask",
        reason="follow up",
        enhanced_question="Run with sample data",
        metadata={"wants_sample_run": True, "workflow_name": "Comms Messages High-Risk Summary"},
        source="follow_up_run",
    )
    clar = assess_route_clarification(
        route,
        "yes please",
        thread_context=thread,
        has_workflow=True,
        canvas_workflow={"name": "Comms Messages High-Risk Summary", "nodes": [{"id": "n1"}]},
    )
    assert clar.needed is False


def test_advisory_how_to_skips_clarification() -> None:
    msg = "How do I export workflow results to CSV or Excel?"
    route = SherpaRoute(
        intent="ask",
        reason="platform Q&A",
        enhanced_question=msg,
        metadata={
            "intent_layer_clarify": True,
            "intent_layer_questions": [
                {
                    "id": "q1",
                    "kind": "choice",
                    "question": "Existing workflow or create new?",
                    "options": [{"id": "c", "label": "Just exploring", "description": "General info"}],
                }
            ],
            "sherpa_disposition": "clarify",
        },
        source="llm",
    )
    clar = assess_route_clarification(route, msg, has_workflow=False)
    assert clar.needed is False


def test_explicit_build_skips_clarification() -> None:
    route = SherpaRoute(
        intent="build",
        reason="new pipeline",
        enhanced_question="Load comms_messages, filter score > 0.7, export csv",
        metadata={},
        source="llm",
    )
    clar = assess_route_clarification(
        route,
        "Load comms_messages, filter high-risk rows with relevance_score > 0.7, and export a CSV summary file",
        thread_context="",
        has_workflow=False,
    )
    assert clar.needed is False


def test_resolve_yes_confirms_sample_run() -> None:
    pending = {
        "intent": "ask",
        "reason": "offer",
        "enhanced_question": "Run sample",
        "metadata": {"wants_sample_run": True},
        "source": "follow_up_run",
    }
    out = resolve_clarification_selection(
        selection_id="yes",
        other_text=None,
        pending_route=pending,
        message="yes please",
        clarification_kind="confirm",
    )
    assert out["metadata"]["wants_sample_run"] is True
    assert out["metadata"]["clarification_resolved"] is True
    assert out["source"] == "clarification_confirmed_run"


def test_resolve_no_declines_action() -> None:
    out = resolve_clarification_selection(
        selection_id="no",
        other_text=None,
        pending_route={"intent": "build", "metadata": {}, "enhanced_question": "x"},
        message="yes",
        clarification_kind="confirm",
    )
    assert out["intent"] == "ask"
    assert out["metadata"].get("wants_sample_run") is False


def test_yes_typo_eys_routes_sample_run_without_confirm() -> None:
    thread = (
        "Sherpa: Built **Comms Messages High-Risk Summary**.\n\n"
        "**Next step:** Run **Comms Messages High-Risk Summary** with sample data.\n\n"
        "Want me to start a sample run now?"
    )
    route = SherpaRoute(
        intent="build",
        reason="x",
        enhanced_question="eys",
        metadata={},
        source="llm",
    )
    out = __import__("copilot.llm_router", fromlist=["finalize_sherpa_route"]).finalize_sherpa_route(
        route,
        message="eys",
        thread_context=thread,
        canvas_workflow={"name": "Comms Messages High-Risk Summary", "nodes": [{}]},
    )
    assert out.metadata.get("wants_sample_run") is True
    clar = assess_route_clarification(
        out,
        "eys",
        thread_context=thread,
        has_workflow=True,
        canvas_workflow={"name": "Comms Messages High-Risk Summary", "nodes": [{}]},
    )
    assert clar.needed is False


def test_comms_build_then_yes_runs_without_confirm() -> None:
    """After build summary, 'yes' should proceed like /run (no Questions gate)."""
    assistant = (
        "Comms Messages High-Risk Summary\n\n"
        "**Next step:** Run **Comms Messages High-Risk Summary** with sample data to preview the export.\n\n"
        "Want me to start a sample run now?"
    )
    thread = (
        "User: Load comms_messages, filter high-risk rows, and export a CSV summary.\n"
        f"Sherpa: {assistant}"
    )
    wf = {"name": "Comms Messages High-Risk Summary", "nodes": [{"id": "n1", "type": "db_query"}]}
    from copilot.llm_router import finalize_sherpa_route, route_sherpa_message

    route = finalize_sherpa_route(
        route_sherpa_message(
            "yes",
            has_workflow=True,
            thread_context=thread,
            canvas_workflow=wf,
        ),
        message="yes",
        thread_context=thread,
        canvas_workflow=wf,
    )
    assert route.intent == "ask"
    assert route.metadata.get("wants_sample_run") is True
    clar = assess_route_clarification(route, "yes", thread_context=thread, has_workflow=True, canvas_workflow=wf)
    assert clar.needed is False


def test_explain_run_with_canvas_skips_clarification() -> None:
    route = SherpaRoute(
        intent="explain_run",
        reason="run review",
        enhanced_question='Review the latest run of "Orders Report".',
        metadata={"workflow_name": "Orders Report"},
        source="llm",
    )
    clar = assess_route_clarification(
        route,
        'Review the latest run of "Orders Report" and suggest one change.',
        thread_context="",
        has_workflow=True,
        canvas_workflow={"name": "Orders Report", "nodes": [{"id": "n1"}]},
    )
    assert clar.needed is False


def test_choice_on_explain_run_preserves_intent_and_answer() -> None:
    pending = {
        "intent": "explain_run",
        "reason": "run review",
        "enhanced_question": 'Review the latest run of "Orders Report".',
        "metadata": {"workflow_name": "Orders Report"},
        "source": "llm",
    }
    out = resolve_clarification_selection(
        selection_id="a",
        other_text=None,
        pending_route=pending,
        message='Review the latest run of "Orders Report".',
        clarification_kind="choice",
        clarification_question="Did you create this workflow on the canvas?",
        selection_label="I created it on the canvas",
        selection_description="Use the workflow currently on the canvas",
    )
    assert out["intent"] == "explain_run"
    assert out["metadata"]["clarification_answer"]
    assert "created it on the canvas" in out["metadata"]["clarification_answer"]
    assert not out["metadata"].get("wants_sql")


def test_resolve_create_choice_routes_to_plan_phase() -> None:
    pending = {
        "intent": "load",
        "reason": "not found",
        "enhanced_question": "Fix the FX pipeline workflow",
        "metadata": {"workflow_name": "FX Pipeline"},
        "source": "llm",
    }
    out = resolve_clarification_selection(
        selection_id="a",
        other_text=None,
        pending_route=pending,
        message="Fix the FX pipeline workflow",
        clarification_kind="choice",
        clarification_question="I could not find that workflow. What should I do?",
        selection_label="Create a new workflow",
        selection_description="Build it on the canvas from your request",
    )
    assert out["intent"] == "ask"
    assert out["metadata"].get("propose_build_plan") is True
    assert out["metadata"].get("build_plan_confirmed") is False
    assert out["metadata"].get("edit_existing_workflow") is False
    assert out["metadata"].get("clarification_answer")
    assert "create" in out["metadata"]["clarification_answer"].lower()
    assert out["source"] == "clarification_create_plan"
    assert "plan only" in (out.get("enhanced_question") or "").lower()


def test_new_build_target_name_skips_workflow_not_found() -> None:
    """Invented target name for a new build must not trigger workflow-not-found."""
    route = SherpaRoute(
        intent="ask",
        reason="plan",
        enhanced_question="Plan only",
        metadata={
            "propose_build_plan": True,
            "workflow_name": "Orders Top Contributors Excel Report",
        },
        source="build_plan_gate",
    )
    clar = assess_route_clarification(
        route,
        "Also export to GitHub",
        thread_context="",
        has_workflow=False,
        canvas_workflow=None,
    )
    assert clar.needed is False


def test_named_run_request_skips_workflow_not_found() -> None:
    """Run 'Workflow' with sample must not block on workflow-not-found clarify."""
    route = SherpaRoute(
        intent="explain_run",
        reason="run",
        enhanced_question="Run and explain",
        metadata={"workflow_name": "Orders Top Contributors Excel Report"},
        source="llm",
    )
    clar = assess_route_clarification(
        route,
        'Run "Orders Top Contributors Excel Report" with sample alert context and explain anything that fails.',
        thread_context="",
        has_workflow=False,
        canvas_workflow=None,
    )
    assert clar.needed is False


def test_named_draft_in_library_skips_workflow_not_found(monkeypatch) -> None:
    """Questions about a named draft/saved workflow must not claim it is missing."""
    monkeypatch.setattr(
        "copilot.intent_clarification._workflow_exists_in_library",
        lambda name: name == "Orders Top Regions",
    )
    route = SherpaRoute(
        intent="ask",
        reason="workflow question",
        enhanced_question="What does the Orders Top Regions workflow do?",
        metadata={"workflow_name": "Orders Top Regions"},
        source="llm",
    )
    clar = assess_route_clarification(
        route,
        "Tell me about the Orders Top Regions workflow",
        thread_context="",
        has_workflow=False,
        canvas_workflow=None,
    )
    assert clar.needed is False


def test_short_affirmation_without_footer_needs_confirm() -> None:
    thread = "User: build\nSherpa: Built **Foo** (3 nodes) on the canvas."
    route = SherpaRoute(intent="build", reason="x", enhanced_question="yes", metadata={}, source="llm")
    clar = assess_route_clarification(
        route,
        "yes please",
        thread_context=thread,
        has_workflow=False,
    )
    assert clar.needed is True
    assert clar.kind == "confirm"
