"""Smoke tests for plan → Questions-panel approval → canvas build routing."""
from __future__ import annotations

from copilot.build_plan_gate import gate_route_to_build_plan_phase, has_build_plan_content
from copilot.intent_clarification import (
    PLAN_APPROVAL_QUESTION_ID,
    assess_route_clarification,
    build_plan_approval_clarification,
    resolve_clarification_answers,
)
from copilot.llm_router import SherpaRoute

BUILD_PROMPT = (
    "Build a workflow that loads orders from a CSV, aggregates revenue by region, "
    "filters high-revenue regions, and exports an Excel report."
)

SIMULATED_PLAN = (
    "I will wait for your confirmation before creating on the canvas.\n\n"
    "Plan:\n"
    "1. Load orders data from CSV extract\n"
    "2. Aggregate revenue by region with group_by\n"
    "3. Filter regions above the revenue threshold\n"
    "4. Sort top contributors\n"
    "5. Generate Excel output report"
)


def _route_natural_language_build() -> SherpaRoute:
    route = SherpaRoute(
        intent="build",
        reason="new workflow",
        enhanced_question=BUILD_PROMPT,
        metadata={"edit_existing_workflow": False},
        source="llm",
    )
    return gate_route_to_build_plan_phase(route, BUILD_PROMPT)


def test_smoke_natural_language_build_skips_pre_clarify_and_plans_first() -> None:
    """Prompt 1: natural-language build should plan first, not ask lame pre-questions."""
    routed = _route_natural_language_build()
    assert routed.intent == "ask"
    assert routed.metadata.get("propose_build_plan") is True
    assert routed.metadata.get("build_plan_confirmed") is False

    clar = assess_route_clarification(routed, BUILD_PROMPT, has_workflow=False)
    assert clar.needed is False


def test_smoke_plan_content_gates_approval_question() -> None:
    """Prompt 2: approval only when a numbered plan was actually shown."""
    assert has_build_plan_content(SIMULATED_PLAN) is True
    assert has_build_plan_content("I will wait for your go-ahead before building.") is False

    clar = build_plan_approval_clarification(workflow_name="Orders Top Regions")
    assert clar.needed is True
    assert clar.questions[0].id == PLAN_APPROVAL_QUESTION_ID
    assert "Does this plan look good" in clar.questions[0].question


def test_smoke_approve_plan_routes_to_canvas_build() -> None:
    """Prompt 3: Approve should route to harness build (canvas), not run-output explain."""
    clar = build_plan_approval_clarification(workflow_name="Orders Top Regions")
    pending = {
        "intent": "ask",
        "reason": "plan",
        "enhanced_question": "plan only",
        "metadata": {
            "propose_build_plan": True,
            "original_user_request": BUILD_PROMPT,
            "workflow_name": "Orders Top Regions",
        },
        "source": "build_plan_gate",
    }
    resolved = resolve_clarification_answers(
        answers=[
            {
                "question_id": PLAN_APPROVAL_QUESTION_ID,
                "question": clar.questions[0].question,
                "kind": "confirm",
                "selection_ids": ["a"],
                "selection_labels": ["Approve"],
            }
        ],
        pending_route=pending,
        message=BUILD_PROMPT,
    )
    assert resolved["intent"] == "build"
    assert resolved["metadata"].get("build_plan_confirmed") is True
    assert resolved["metadata"].get("propose_build_plan") is False

    final = gate_route_to_build_plan_phase(
        SherpaRoute(
            intent=str(resolved["intent"]),
            reason=str(resolved.get("reason") or ""),
            enhanced_question=str(resolved.get("enhanced_question") or BUILD_PROMPT),
            metadata=dict(resolved.get("metadata") or {}),
            source=str(resolved.get("source") or ""),
        ),
        "Approve",
    )
    assert final.intent == "build"


def test_approve_without_question_id_still_routes_to_build() -> None:
    """Frontend-style approve text must not fall through to a second plan phase."""
    pending = {
        "intent": "ask",
        "metadata": {
            "propose_build_plan": True,
            "original_user_request": BUILD_PROMPT,
            "workflow_name": "Orders Top Regions",
        },
        "source": "build_plan_gate",
    }
    resolved = resolve_clarification_answers(
        answers=[
            {
                "question": "Approve this plan and create **Orders Top Regions** on the canvas?",
                "kind": "confirm",
                "selection_ids": ["a"],
                "selection_labels": ["Approve"],
            }
        ],
        pending_route=pending,
        message=BUILD_PROMPT,
    )
    assert resolved["intent"] == "build"
    assert resolved["metadata"].get("build_plan_confirmed") is True
    assert resolved["metadata"].get("propose_build_plan") is False


def test_yes_on_create_confirm_during_plan_phase_routes_to_build() -> None:
    """Yes — Proceed on a plan-phase confirm must not re-enter ask/plan chat."""
    pending = {
        "intent": "ask",
        "metadata": {
            "propose_build_plan": True,
            "original_user_request": BUILD_PROMPT,
            "workflow_name": "Orders Top Contributors Excel Report",
        },
        "source": "build_plan_gate",
    }
    resolved = resolve_clarification_answers(
        answers=[
            {
                "question": (
                    'I can create a new workflow named "Orders Top Contributors Excel Report" '
                    "with the following steps. Does this plan look good?"
                ),
                "kind": "confirm",
                "selection_ids": ["yes"],
                "selection_labels": ["Yes"],
            }
        ],
        pending_route=pending,
        message=BUILD_PROMPT,
    )
    assert resolved["intent"] == "build"
    assert resolved["metadata"].get("build_plan_confirmed") is True
    assert resolved["metadata"].get("propose_build_plan") is False


def test_smoke_reject_plan_keeps_plan_phase() -> None:
    """Prompt 4: Reject should not build; user can revise the plan."""
    pending = {
        "intent": "ask",
        "metadata": {
            "propose_build_plan": True,
            "original_user_request": BUILD_PROMPT,
        },
        "source": "build_plan_gate",
    }
    resolved = resolve_clarification_answers(
        answers=[
            {
                "question_id": PLAN_APPROVAL_QUESTION_ID,
                "question": "Does this plan look good?",
                "kind": "confirm",
                "selection_ids": ["b"],
                "selection_labels": ["Reject"],
                "other_text": "Also export to GitHub and add total/average columns",
            }
        ],
        pending_route=pending,
        message=BUILD_PROMPT,
    )
    assert resolved["intent"] == "ask"
    assert resolved["metadata"].get("propose_build_plan") is True
    assert resolved["metadata"].get("build_plan_confirmed") is False
    assert resolved["source"] == "clarification_plan_rejected"
    assert resolved["metadata"].get("awaiting_plan_revision") is True
    assert "GitHub" in (resolved.get("enhanced_question") or "")
