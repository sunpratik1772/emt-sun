"""Regression tests for difficult Sherpa prompts and sequences."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.routers.copilot import _classify_response_from_result
from copilot.build_plan_gate import gate_route_to_build_plan_phase
from copilot.llm_router import route_sherpa_message
from tests.intent_disposition_matrix_cases import DispositionMatrixCase
from tests.regression_disposition_cases import REGRESSION_DISPOSITION_CASES, RegressionCase
from tests.test_intent_disposition_matrix_live import (
    _assert_case,
    _classify_case,
    _gemini_configured,
    _thread_context,
)

_BACKEND = Path(__file__).resolve().parents[1]

OFFLINE_REGRESSION = frozenset({
    "R01_load_phantom",
    "R02_run_phantom_sample",
    "R03_review_phantom_run",
    "R04_improve_phantom",
    "R05_load_orders_exists",
    "R06_edit_orders_on_canvas",
    "R07_delta_edit_canvas",
    "R08_github_confluence_build",
    "R10_slash_improve_github",
    "R11_offtopic_weather",
    "R13_platform_capabilities",
    "R14_sequence_run_review_plan",
    "R18_export_how_to_starter",
})


def _classify_regression(case: RegressionCase):
    return _classify_case(case)


@pytest.mark.parametrize(
    "case",
    REGRESSION_DISPOSITION_CASES,
    ids=[c.case_id for c in REGRESSION_DISPOSITION_CASES],
)
def test_regression_disposition_offline(case: RegressionCase, monkeypatch) -> None:
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    monkeypatch.setattr("copilot.intent_clarification.gemini_configured", lambda: False)
    monkeypatch.setattr("copilot.intent_layer.gemini_configured", lambda: False)
    if case.case_id not in OFFLINE_REGRESSION:
        pytest.skip("live or LLM-heavy regression case")
    resp = _classify_regression(case)
    _assert_case(case, resp)


@pytest.mark.live
@pytest.mark.parametrize(
    "case",
    REGRESSION_DISPOSITION_CASES,
    ids=[c.case_id for c in REGRESSION_DISPOSITION_CASES],
)
def test_regression_disposition_live(case: RegressionCase) -> None:
    if not _gemini_configured():
        pytest.skip("GEMINI_API_KEY not configured")
    resp = _classify_regression(case)
    _assert_case(case, resp)
