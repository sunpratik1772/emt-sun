"""Live matrix: full /copilot/route pipeline (router + plan gate + intent layer + clarify)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.routers.copilot import _classify_response_from_result
from copilot.build_plan_gate import gate_route_to_build_plan_phase
from copilot.llm_router import route_sherpa_message
from tests.intent_disposition_matrix_cases import INTENT_DISPOSITION_MATRIX, DispositionMatrixCase

_BACKEND = Path(__file__).resolve().parents[1]


def _gemini_configured() -> bool:
    try:
        from llm import gemini_configured, gemini_api_key

        key = gemini_api_key()
        if not key or key == "mock_key_for_testing":
            return False
        return bool(gemini_configured())
    except Exception:
        key = os.environ.get("GEMINI_API_KEY", "")
        return bool(key) and key != "mock_key_for_testing"


def _thread_context(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = "User" if m.get("role") == "user" else "Sherpa"
        lines.append(f"{role}: {m.get('content', '')}")
    return "\n".join(lines)


def _classify_case(case: DispositionMatrixCase):
    thread_ctx = _thread_context(case.thread_messages) if case.thread_messages else None
    route = route_sherpa_message(
        case.message,
        has_workflow=case.has_workflow,
        workflow_name=case.workflow_name,
        has_run_log=case.has_run_log,
        run_workflow_name=case.workflow_name,
        thread_context=thread_ctx,
        canvas_workflow=case.current_workflow,
    )
    route = gate_route_to_build_plan_phase(route, case.message)
    return _classify_response_from_result(
        route,
        message=case.message,
        thread_context=thread_ctx,
        has_workflow=case.has_workflow,
        canvas_workflow=case.current_workflow,
    )


def _assert_case(case: DispositionMatrixCase, resp) -> None:
    meta = resp.metadata
    disp = (resp.disposition.kind if resp.disposition else None) or meta.sherpa_disposition
    clarify_needed = bool(resp.clarification and resp.clarification.needed)

    if case.expected_intent:
        assert resp.intent == case.expected_intent, (
            f"intent {resp.intent!r} != {case.expected_intent!r}; reason={resp.reason}"
        )
    if case.allowed_intents:
        assert resp.intent in case.allowed_intents, (
            f"intent {resp.intent!r} not in {case.allowed_intents}; reason={resp.reason}"
        )

    if case.expected_disposition != "any":
        assert disp == case.expected_disposition, (
            f"disposition {disp!r} != {case.expected_disposition!r}; reason={resp.reason}"
        )

    if case.expect_clarify == "yes":
        assert clarify_needed, f"expected clarification; reason={resp.reason}"
    elif case.expect_clarify == "no":
        assert not clarify_needed, (
            f"unexpected clarification: {(resp.clarification.questions or [{}])[0].question if resp.clarification else ''}"
        )

    if case.expect_propose_build_plan is not None:
        assert bool(meta.propose_build_plan) == case.expect_propose_build_plan

    if case.expect_propose_fix_plan is not None:
        assert bool(meta.propose_fix_plan) == case.expect_propose_fix_plan

    if case.expect_wants_sample_run is not None:
        assert bool(meta.wants_sample_run) == case.expect_wants_sample_run

    if case.expect_edit_existing is not None:
        assert bool(meta.edit_existing_workflow) == case.expect_edit_existing

    if case.extra_check:
        case.extra_check(resp)


@pytest.mark.live
@pytest.mark.parametrize(
    "case",
    INTENT_DISPOSITION_MATRIX,
    ids=[c.case_id for c in INTENT_DISPOSITION_MATRIX],
)
def test_intent_disposition_matrix_live(case: DispositionMatrixCase) -> None:
    if not _gemini_configured():
        pytest.skip("GEMINI_API_KEY not configured for live matrix")
    resp = _classify_case(case)
    _assert_case(case, resp)


@pytest.mark.parametrize("case", INTENT_DISPOSITION_MATRIX, ids=[c.case_id for c in INTENT_DISPOSITION_MATRIX])
def test_intent_disposition_matrix_offline_heuristics(case: DispositionMatrixCase, monkeypatch) -> None:
    """Offline: cases with strong heuristic overrides must pass without Gemini."""
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    monkeypatch.setattr("copilot.intent_clarification.gemini_configured", lambda: False)
    offline_only = {
        "02_show_fix_plan_followup",
        "03_sample_run_yes",
        "04_canvas_edit_yes",
        "08_named_run_sample",
        "09_improve_existing_named",
        "13_do_it_after_run_review",
        "17_slash_style_build",
    }
    if case.case_id not in offline_only:
        pytest.skip("heuristic-only subset")
    resp = _classify_case(case)
    _assert_case(case, resp)
