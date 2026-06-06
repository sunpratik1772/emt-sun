"""Tests for LLM copilot intent routing."""
from __future__ import annotations

import json

import pytest

from copilot.intent_router import classify_copilot_intent


class StubAdapter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def chat_turn(self, **kwargs):
        self.calls.append(kwargs)
        return json.dumps(self.payload)


def test_llm_routes_resource_question_to_ask(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "ask",
            "reason": "User wants a list of skills, not a workflow.",
        }
    )
    result = classify_copilot_intent(
        "Show me the available FinCrime skills I can use in a workflow.",
        adapter=adapter,
    )
    assert result.intent == "ask"
    assert result.source == "llm"
    assert adapter.calls


def test_llm_routes_pipeline_instruction_to_build(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "intent": "build",
            "reason": "User wants a csv_extract → filter → csv_output pipeline.",
        }
    )
    result = classify_copilot_intent(
        "Use csv_extract on leads.csv, filter score > 80, save with csv_output.",
        adapter=adapter,
    )
    assert result.intent == "build"
    assert result.source == "llm"


def test_heuristic_routes_automation_request(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    result = classify_copilot_intent(
        "Create an automation of the workflow that you just created and run it at 9:30 AM each morning. Test it out.",
        has_workflow=True,
    )
    assert result.intent == "automate"
    assert result.source == "heuristic"


def test_heuristic_fallback_when_llm_unavailable(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    result = classify_copilot_intent(
        "Show me the available FinCrime skills I can use in a workflow.",
    )
    assert result.intent == "ask"
    assert result.source == "heuristic"


def test_heuristic_routes_load_request(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    result = classify_copilot_intent("Open the leads pipeline workflow", has_workflow=False)
    assert result.intent == "load"
    assert result.source == "heuristic"


def test_llm_classifier_receives_thread_context(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: True)
    adapter = StubAdapter({"intent": "automate", "reason": "Follow-up schedule request."})
    thread = "User: Build a csv pipeline\nSherpa: Built **Leads** (3 nodes)"
    classify_copilot_intent(
        "Automate it at 9:30 AM daily",
        has_workflow=True,
        thread_context=thread,
        adapter=adapter,
    )
    assert adapter.calls
    assert "Recent conversation" in adapter.calls[0]["user_turn"]
    assert "Built **Leads**" in adapter.calls[0]["user_turn"]


def test_workflow_copilot_classify_forwards_canvas_workflow(monkeypatch):
    monkeypatch.setattr("copilot.llm_router.gemini_configured", lambda: False)
    from copilot.workflow_generator import WorkflowCopilot

    cp = WorkflowCopilot()
    result = cp.classify_intent(
        "Create an Excel report from orders.csv with sorted top contributors.",
        canvas_workflow={"name": "Orders", "nodes": [{"id": "n1"}], "edges": []},
    )
    assert result.intent == "build"
