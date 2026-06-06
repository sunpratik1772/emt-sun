"""Live Gemini tests for Sherpa LLM router."""
from __future__ import annotations

import os

import pytest

from copilot.llm_router import route_sherpa_message


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


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
class TestLiveLlmRouter:
    def test_routes_reliability_review_to_explain_run(self) -> None:
        route = route_sherpa_message(
            'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
            "and suggest one change to improve reliability.",
            recent_run_workflows=["Join Comms Messages with HS Alerts and Rank"],
        )
        assert route.intent == "explain_run", f"got {route.intent}: {route.reason}"
        wf = (route.metadata or {}).get("workflow_name") or ""
        assert "join comms" in wf.lower() or "comms" in wf.lower()
        assert route.enhanced_question.strip()

    def test_routes_build_pipeline_request(self) -> None:
        route = route_sherpa_message(
            "Need to create a new workflow that loads comms, joins alerts, ranks by score.",
        )
        assert route.intent == "build", f"got {route.intent}: {route.reason}"

    def test_routes_improve_workflow_to_build(self) -> None:
        msg = (
            'Improve "Join Comms Messages with HS Alerts and Rank" with validation, '
            'a branch for failures, and an Outlook summary when the run completes.'
        )
        route = route_sherpa_message(msg, recent_run_workflows=["Join Comms Messages with HS Alerts and Rank"])
        assert route.intent == "build", f"got {route.intent}: {route.reason}"
        assert route.metadata.get("edit_existing_workflow") is True
        wf = route.metadata.get("workflow_name") or ""
        assert "comms" in wf.lower()
        eq = route.enhanced_question.lower()
        assert "outlook" in eq or "outlook" in " ".join(route.keywords).lower()
        assert "validation" in eq or "valid" in eq

    def test_routes_error_diagnosis(self) -> None:
        route = route_sherpa_message(
            "Why did the join node fail on my last run?",
            has_run_log=True,
            recent_errors=[{"message": "join node error", "node_id": "n04"}],
        )
        assert route.intent in {"explain_error", "explain_run"}, f"got {route.intent}"
