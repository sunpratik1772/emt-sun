"""Tests for the unified Sherpa intent layer."""
from __future__ import annotations

from copilot.intent_layer import (
    _disposition_from_router_meta,
    action_follow_up_show_fix_plan_override,
    resolve_sherpa_disposition,
)
from copilot.llm_router import SherpaRoute, _parse_route, finalize_sherpa_route


def test_show_fix_plan_after_run_review() -> None:
    thread = (
        "User: Review the latest run of \"Orders Top Contributors Excel Report\"\n"
        "Sherpa: **Orders Top Contributors Excel Report Run Summary**\n"
        "Draft Email for Stakeholders (agent): did not execute.\n\n"
        "**Next step:** Update the workflow to ensure the 'Draft Email for Stakeholders' "
        "node (n08) executes as intended.\n\n"
        "Want me to check the connections to node n08?"
    )
    ov = action_follow_up_show_fix_plan_override(
        "ok show the plan",
        thread_context=thread,
        canvas_workflow={"name": "Orders Top Contributors Excel Report", "nodes": []},
    )
    assert ov is not None
    assert ov["intent"] == "ask"
    assert ov["metadata"]["propose_fix_plan"] is True
    assert ov["metadata"]["propose_build_plan"] is True
    assert "Plan only" in ov["enhanced_question"]
    assert "n08" in ov["enhanced_question"] or "Draft Email" in ov["enhanced_question"]


def test_finalize_routes_show_plan_to_fix_not_build() -> None:
    thread = (
        "Sherpa: Run Summary\n"
        "**Next step:** Update the workflow to ensure node n08 executes.\n\n"
        "Want me to check connections?"
    )
    out = finalize_sherpa_route(
        SherpaRoute(
            intent="build",
            reason="misroute",
            enhanced_question="show plan",
            metadata={"edit_existing_workflow": True},
            source="llm",
        ),
        message="ok show the plan",
        thread_context=thread,
        canvas_workflow={"name": "Orders Top Contributors Excel Report", "nodes": [{"id": "n08"}]},
    )
    assert out.intent == "ask"
    assert out.metadata.get("propose_fix_plan") is True
    assert out.source == "follow_up_show_fix_plan"


def test_explain_run_disposition_is_answer() -> None:
    route = SherpaRoute(
        intent="explain_run",
        reason="run review",
        enhanced_question="Review latest run",
        metadata={"workflow_name": "Orders Top Contributors Excel Report"},
        source="llm",
    )
    _, disp = resolve_sherpa_disposition(
        route,
        "Review the latest run and suggest one reliability fix",
        has_workflow=True,
        canvas_workflow={"name": "Orders Top Contributors Excel Report", "nodes": []},
    )
    assert disp.kind == "answer"
    assert "run" in disp.thinking.lower()


def test_parse_route_bundles_disposition() -> None:
    route = _parse_route(
        {
            "intent": "explain_run",
            "reason": "run review",
            "enhanced_question": "Review run",
            "thinking": "Pulling run log.\nScanning nodes.\nWriting summary.",
            "disposition": "answer",
            "confidence": 0.91,
            "keywords": [],
            "metadata": {},
        },
        fallback_message="Review run",
        source="llm",
    )
    assert route.metadata.get("router_disposition") == "answer"
    assert "Pulling run log" in route.metadata.get("thinking_preview", "")
    disp = _disposition_from_router_meta(route.metadata)
    assert disp is not None
    assert disp.kind == "answer"
    assert disp.thinking.startswith("Pulling run log")


def test_router_disposition_skips_second_llm_layer() -> None:
    route = SherpaRoute(
        intent="ask",
        reason="docs",
        enhanced_question="What nodes exist?",
        metadata={
            "router_disposition": "answer",
            "router_thinking": "I'll answer from the node catalog.\nChecking palette.\nDrafting now.",
            "disposition_confidence": 0.88,
        },
        source="llm",
    )
    _, disp = resolve_sherpa_disposition(
        route,
        "explain_run row counts for the orders workflow",
        has_workflow=True,
    )
    assert disp.kind == "answer"
    assert "node catalog" in disp.thinking.lower()
    assert disp.reason == "Router disposition"


def test_advisory_export_question_overrides_router_clarify() -> None:
    msg = "How do I export workflow results to CSV or Excel?"
    route = SherpaRoute(
        intent="ask",
        reason="LLM over-clarified",
        enhanced_question=msg,
        metadata={
            "router_disposition": "clarify",
            "router_clarify_questions": [
                {
                    "id": "q1",
                    "kind": "choice",
                    "question": "Are you looking to export from an existing workflow or create a new one?",
                    "options": [
                        {"id": "a", "label": "Existing workflow", "description": "Name a workflow"},
                        {"id": "c", "label": "Just exploring", "description": "General information"},
                    ],
                }
            ],
        },
        source="llm",
    )
    route2, disp = resolve_sherpa_disposition(route, msg, has_workflow=False)
    assert disp.kind == "answer"
    assert route2.intent == "ask"
    assert not route2.metadata.get("intent_layer_clarify")


def test_short_new_build_disposition_clarify_or_plan() -> None:
    route = SherpaRoute(
        intent="build",
        reason="new pipeline",
        enhanced_question="build a report",
        metadata={},
        source="llm",
    )
    _, disp = resolve_sherpa_disposition(
        route,
        "build a report",
        has_workflow=False,
        canvas_workflow=None,
    )
    assert disp.kind in ("clarify", "plan")
