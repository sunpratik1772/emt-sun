"""Tests for Sherpa LLM router structured output."""
from __future__ import annotations

import json

import pytest

from copilot.llm_router import route_sherpa_message


class StubAdapter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_turn(self, **kwargs):
        return json.dumps(self.payload)


def test_router_parses_explain_run_with_metadata(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "explain_run",
            "reason": "Reliability review of named workflow run",
            "enhanced_question": "Review latest Join Comms run for reliability improvements.",
            "keywords": ["reliability", "join", "latest run"],
            "metadata": {
                "workflow_name": "Join Comms Messages with HS Alerts and Rank",
                "run_selector": "latest",
                "suggested_sql": (
                    "SELECT COUNT(*) AS joined_rows FROM run_output"
                ),
            },
        }
    )
    route = route_sherpa_message(
        'Review the latest run of "Join Comms Messages with HS Alerts and Rank" '
        "and suggest one change to improve reliability.",
        adapter=adapter,
    )
    assert route.intent == "explain_run"
    assert route.source == "llm"
    assert "Join Comms" in route.enhanced_question
    assert route.metadata.get("workflow_name")
    assert route.metadata.get("run_selector") == "latest"
    assert "reliability" in route.keywords


def test_router_coalesces_query_run_data_to_explain_run(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "query_run_data",
            "reason": "Row count and ranking question",
            "enhanced_question": "How many rows were produced and who is the top trader?",
            "keywords": ["rows", "trader"],
            "metadata": {"wants_sql": True, "verification_plan": ["row_counts"]},
        }
    )
    route = route_sherpa_message(
        "How many rows were produced and who is the top trader by total relevance?",
        has_run_log=True,
        adapter=adapter,
    )
    assert route.intent == "explain_run"


def test_router_keeps_explicit_sql_as_query_run_data(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "query_run_data",
            "reason": "Explicit SQL",
            "enhanced_question": "Run trader count SQL on latest output",
            "keywords": [],
            "metadata": {"wants_sql": True},
        }
    )
    msg = (
        "On the latest run, run: "
        "SELECT trader_name, COUNT(*) AS n FROM run_output GROUP BY trader_name"
    )
    route = route_sherpa_message(msg, adapter=adapter)
    assert route.intent == "query_run_data"


def test_router_named_run_with_sample_overrides_to_sample_run(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "explain_run",
            "reason": "Run and explain failures",
            "enhanced_question": "Explain run failures",
            "keywords": [],
            "metadata": {"workflow_name": "Orders Top Contributors Excel Report"},
        }
    )
    route = route_sherpa_message(
        'Run "Orders Top Contributors Excel Report" with sample alert context '
        "and explain anything that fails.",
        adapter=adapter,
    )
    assert route.intent == "ask"
    assert route.metadata.get("wants_sample_run") is True
    assert route.metadata.get("workflow_name") == "Orders Top Contributors Excel Report"
    assert route.source == "heuristic_named_run"


def test_router_heuristic_explain_run_when_no_gemini(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    route = route_sherpa_message(
        "Review the latest run and suggest one reliability improvement.",
        has_run_log=True,
    )
    assert route.intent == "explain_run"
    assert route.source == "heuristic"


def test_router_named_load_onto_canvas_without_workflow_word(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    route = route_sherpa_message(
        'Load "Orders Top Contributors Excel Report" onto the canvas',
        has_workflow=False,
    )
    assert route.intent == "load"
    assert route.metadata.get("workflow_name") == "Orders Top Contributors Excel Report"
    assert route.source in ("heuristic", "heuristic_named_load")
