"""Live Gemini: full suggestion-type matrix for Sherpa router + run analyst."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from copilot.llm_router import route_sherpa_message
from copilot.run_analyst import stream_run_execution_summary
from copilot.run_dataset_memory import replay_workflow_rows
from tests.sherpa_router_cases import SHERPA_ROUTER_CASES

_BACKEND = Path(__file__).resolve().parents[1]
_FIXTURE_DB = _BACKEND / "demo_data" / "surveillance_fixture.sqlite"

_COMMS_WORKFLOW = {
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
            "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
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

_ANALYST_CASES = [
    {
        "case_id": "analyst_reliability",
        "message": (
            'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
            "and suggest one change to improve reliability."
        ),
        "must_contain_any": ("join", "inner", "left", "alert", "reliability"),
    },
    {
        "case_id": "analyst_row_count",
        "message": "How many rows were produced and who is the top trader by total relevance?",
        "must_contain_any": ("500", "riley", "trader", "row"),
    },
]


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


def _run_log_with_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "node_id": "n02",
            "label": "Load Comms",
            "node_type": "db_query",
            "status": "ok",
            "duration_ms": 10,
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
        {
            "node_id": "n04",
            "label": "Join",
            "node_type": "join",
            "status": "ok",
            "duration_ms": 20,
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
    ]


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
class TestSherpaSuggestionMatrixLive:
    """Serial live-Gemini matrix — one case at a time to respect rate limits."""

    @pytest.fixture(autouse=True)
    def _rate_limit_gap(self):
        time.sleep(12)
        yield

    @pytest.mark.parametrize(
        "case",
        SHERPA_ROUTER_CASES,
        ids=[c.case_id for c in SHERPA_ROUTER_CASES],
    )
    def test_router_case(self, case) -> None:
        ctx = dict(case.context)
        route = route_sherpa_message(case.message, **ctx)
        assert route.intent in case.expected_intents, (
            f"[{case.case_id}] expected one of {sorted(case.expected_intents)}, "
            f"got {route.intent!r}: {route.reason}"
        )
        assert (route.enhanced_question or "").strip(), f"[{case.case_id}] empty enhanced_question"
        assert route.source == "llm", f"[{case.case_id}] expected llm router, got {route.source}"
        if case.check:
            case.check(route)


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
@pytest.mark.skipif(not _FIXTURE_DB.is_file(), reason="surveillance fixture missing")
class TestSherpaAnalystMatrixLive:
    @pytest.fixture(autouse=True)
    def _rate_limit_gap(self):
        time.sleep(15)
        yield

    @pytest.fixture(scope="class")
    def run_payload(self):
        rows, _ = replay_workflow_rows(_COMMS_WORKFLOW)
        return _COMMS_WORKFLOW, _run_log_with_rows(rows)

    @pytest.mark.parametrize("case", _ANALYST_CASES, ids=[c["case_id"] for c in _ANALYST_CASES])
    def test_analyst_case(self, case, run_payload) -> None:
        workflow, run_log = run_payload
        route = route_sherpa_message(case["message"], has_run_log=True)
        assert route.intent in {"explain_run", "explain_error", "query_run_data"}, route.intent
        chunks: list[str] = []
        text = stream_run_execution_summary(
            workflow,
            run_log,
            None,
            chunks.append,
            user_message=route.enhanced_question or case["message"],
            suggested_sql=(route.metadata or {}).get("suggested_sql"),
        )
        lower = text.lower()
        assert any(k in lower or k in text for k in case["must_contain_any"]), (
            f"[{case['case_id']}] response missing any of {case['must_contain_any']}: {text[:400]}"
        )
