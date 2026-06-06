"""Tests for plan-before-build gate."""
from __future__ import annotations

from copilot.build_plan_gate import (
    build_plan_ask_prompt,
    ensure_build_plan_confirm_footer,
    gate_route_to_build_plan_phase,
    has_build_plan_content,
    message_requests_build_plan,
)
from copilot.intent_clarification import (
    assess_route_clarification,
    build_plan_approval_clarification,
    resolve_clarification_answers,
)
from copilot.follow_up import action_follow_up_create_build_override
from copilot.llm_router import SherpaRoute


def test_gate_redirects_new_build_to_ask_plan() -> None:
    route = SherpaRoute(
        intent="build",
        reason="new",
        enhanced_question="Create Orders pipeline",
        metadata={"edit_existing_workflow": False},
        source="llm",
    )
    out = gate_route_to_build_plan_phase(route, "Create Orders pipeline")
    assert out.intent == "ask"
    assert out.metadata.get("propose_build_plan") is True
    assert "plan only" in (out.enhanced_question or "").lower()


def test_gate_skips_edit_existing_build() -> None:
    route = SherpaRoute(
        intent="build",
        reason="edit",
        enhanced_question="Fix join",
        metadata={"edit_existing_workflow": True},
        source="llm",
    )
    out = gate_route_to_build_plan_phase(route, "Fix join")
    assert out.intent == "build"


def test_plan_footer_offers_create_confirm() -> None:
    body = ensure_build_plan_confirm_footer(
        "Here is the plan:\n1. Load data",
        workflow_name="Orders Top",
    )
    assert "Should I create **Orders Top** on the canvas now" in body


def test_yes_after_plan_footer_routes_to_build() -> None:
    assistant = (
        "Plan:\n1. Load orders\n\n"
        "**Next step:** Create **Orders Top** on the canvas from the plan above.\n\n"
        "Should I create **Orders Top** on the canvas now?"
    )
    thread = "User: Review run\nSherpa: " + assistant
    out = action_follow_up_create_build_override(
        "yes please",
        thread_context=thread,
        canvas_workflow=None,
    )
    assert out is not None
    assert out["intent"] == "build"
    assert out["metadata"].get("build_plan_confirmed") is True


def test_message_requests_build_plan_flag() -> None:
    assert message_requests_build_plan("x", propose_build_plan=True)
    assert message_requests_build_plan(build_plan_ask_prompt("create wf"))


def test_has_build_plan_content_detects_numbered_steps() -> None:
    text = (
        "Here is the plan:\n"
        "1. Load orders CSV\n"
        "2. Aggregate by region\n"
        "3. Export Excel report"
    )
    assert has_build_plan_content(text) is True
    assert has_build_plan_content("Sounds good — I will wait for your go-ahead.") is False


def test_propose_build_plan_skips_pre_clarify() -> None:
    route = SherpaRoute(
        intent="ask",
        reason="plan",
        enhanced_question="Plan only",
        metadata={"propose_build_plan": True},
        source="build_plan_gate",
    )
    clar = assess_route_clarification(route, "Build revenue pipeline", has_workflow=False)
    assert clar.needed is False


def test_plan_approval_yes_routes_to_build() -> None:
    pending = {
        "intent": "ask",
        "reason": "plan",
        "enhanced_question": "Plan only",
        "metadata": {
            "propose_build_plan": True,
            "original_user_request": "Build Orders Top Regions pipeline",
            "workflow_name": "Orders Top",
        },
        "source": "build_plan_gate",
    }
    out = resolve_clarification_answers(
        answers=[
            {
                "question_id": "q_plan_approve",
                "question": "Does this plan look good? Should I create **Orders Top** on the canvas?",
                "kind": "confirm",
                "selection_ids": ["a"],
                "selection_labels": ["Approve"],
            }
        ],
        pending_route=pending,
        message="Build Orders Top Regions pipeline",
    )
    assert out["intent"] == "build"
    assert out["metadata"].get("build_plan_confirmed") is True
    assert out["metadata"].get("propose_build_plan") is False
    assert out["source"] == "clarification_confirmed_build"


def test_build_plan_approval_clarification_shape() -> None:
    clar = build_plan_approval_clarification(workflow_name="Orders Top")
    assert clar.needed is True
    assert clar.questions[0].options[0].label == "Approve"
    assert clar.questions[0].options[1].label == "Reject"
