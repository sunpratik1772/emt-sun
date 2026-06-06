"""Live Gemini tests for run analyst (explain-run path)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from copilot.run_analyst import stream_run_execution_summary
from copilot.run_dataset_memory import replay_workflow_rows
from copilot.llm_router import route_sherpa_message

_BACKEND = Path(__file__).resolve().parents[1]
_FIXTURE_DB = _BACKEND / "demo_data" / "surveillance_fixture.sqlite"

_COMMS_ALERTS_WORKFLOW = {
    "name": "Join Comms Messages with Alerts and Rank",
    "nodes": [
        {"id": "n01", "type": "manual_trigger", "label": "Start"},
        {
            "id": "n02",
            "type": "db_query",
            "label": "Load Comms",
            "config": {
                "source": "comms_messages",
                "query": (
                    "SELECT message_id, alert_id, participant_id, trader_name, "
                    "timestamp, relevance_score FROM comms_messages"
                ),
            },
        },
        {
            "id": "n03",
            "type": "db_query",
            "label": "Load Alerts",
            "config": {
                "source": "hs_alerts",
                "query": (
                    "SELECT alert_id, trader_id, trader_name, keyword, alert_date, scenario "
                    "FROM hs_alerts"
                ),
            },
        },
        {
            "id": "n04",
            "type": "join",
            "label": "Join",
            "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "inner"},
        },
        {
            "id": "n05",
            "type": "sort",
            "label": "Sort",
            "config": {"sortBy": "relevance_score", "order": "desc"},
        },
        {
            "id": "n06",
            "type": "csv_output",
            "label": "CSV",
            "config": {"filename": "ranked_comms_alerts.csv"},
        },
    ],
    "edges": [
        {"from": "n01", "to": "n02"},
        {"from": "n01", "to": "n03"},
        {"from": "n02", "to": "n04"},
        {"from": "n03", "to": "n04"},
        {"from": "n04", "to": "n05"},
        {"from": "n05", "to": "n06"},
    ],
}


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


def _minimal_run_log(rows: list[dict]) -> list[dict]:
    return [
        {"node_id": "n02", "label": "Load Comms", "node_type": "db_query", "status": "ok", "duration_ms": 10,
         "output": {"node_output": {"rows": rows, "rowCount": len(rows)}}},
        {"node_id": "n04", "label": "Join", "node_type": "join", "status": "ok", "duration_ms": 20,
         "output": {"node_output": {"rows": rows, "rowCount": len(rows)}}},
    ]


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
@pytest.mark.skipif(not _FIXTURE_DB.is_file(), reason="surveillance fixture missing")
class TestLiveRunAnalyst:
    @pytest.fixture(autouse=True)
    def _rate_limit_pause(self):
        time.sleep(18)
        yield

    @pytest.fixture
    def run_payload(self):
        rows, _ = replay_workflow_rows(_COMMS_ALERTS_WORKFLOW)
        return _COMMS_ALERTS_WORKFLOW, _minimal_run_log(rows)

    def test_row_count_and_top_trader_question(self, run_payload) -> None:
        workflow, run_log = run_payload
        route = route_sherpa_message(
            "How many rows were produced and who is the top trader by total relevance?",
            has_run_log=True,
        )
        chunks: list[str] = []
        text = stream_run_execution_summary(
            workflow,
            run_log,
            None,
            chunks.append,
            user_message=route.enhanced_question or route.metadata.get("workflow_name") or "",
        )
        lower = text.lower()
        assert "500" in text or "five hundred" in lower or "riley" in lower

    def test_reliability_review_question(self, run_payload) -> None:
        workflow, run_log = run_payload
        prompt = (
            'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
            "and suggest one change to improve reliability."
        )
        route = route_sherpa_message(prompt)
        chunks: list[str] = []
        text = stream_run_execution_summary(
            workflow,
            run_log,
            None,
            chunks.append,
            user_message=route.enhanced_question or prompt,
        )
        lower = text.lower()
        assert any(k in lower for k in ("join", "inner", "left", "alert_id", "reliability"))

    def test_join_row_count_comparison(self, run_payload) -> None:
        workflow, run_log = run_payload
        prompt = "Compare join output row count to loaded comms messages — did we lose any rows?"
        route = route_sherpa_message(prompt, has_run_log=True)
        chunks: list[str] = []
        text = stream_run_execution_summary(
            workflow,
            run_log,
            None,
            chunks.append,
            user_message=route.enhanced_question or prompt,
        )
        assert "500" in text or "row" in text.lower()
