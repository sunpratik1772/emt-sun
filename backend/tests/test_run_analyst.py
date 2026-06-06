"""Tests for copilot.run_analyst summaries."""
from __future__ import annotations

from copilot.run_analyst import (
    _deterministic_design_summary,
    _deterministic_run_summary,
    _run_analysis_prompt,
    stream_run_execution_summary,
)


def test_deterministic_design_summary_lists_nodes() -> None:
    workflow = {
        "name": "Lead Scoring",
        "nodes": [
            {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n2", "type": "csv_extract", "label": "Load Leads", "config": {"source": "leads.csv"}},
            {"id": "n3", "type": "csv_output", "label": "Export", "config": {"filename": "leads_out.csv"}},
        ],
        "edges": [{"from": "n1", "to": "n2"}],
    }
    text = _deterministic_design_summary(workflow, "score leads and export csv")
    assert "**Lead Scoring**" in text
    assert "`leads.csv`" in text
    assert "Steps:" not in text
    assert "Why these choices" not in text
    assert "Built:" not in text


def test_deterministic_run_summary_uses_log() -> None:
    workflow = {"name": "Lead Scoring"}
    log = [{
        "node_id": "n2",
        "node_type": "csv_extract",
        "label": "Load Leads",
        "status": "ok",
        "duration_ms": 12,
        "output": {"datasets": {"default": {"rows": 10}}},
    }]
    text = _deterministic_run_summary(workflow, log, None)
    assert "Run Summary" in text
    assert "Load Leads" in text
    assert "10 row" in text.lower() or "10" in text


def test_run_analysis_prompt_includes_user_question() -> None:
    prompt = _run_analysis_prompt({"run_log": []}, user_message="top 3 traders")
    assert "User question:" in prompt
    assert "top 3 traders" in prompt
    assert "Analyze this completed run:" in prompt


def test_stream_run_summary_empty_log() -> None:
    chunks: list[str] = []
    out = stream_run_execution_summary({"name": "X"}, [], None, chunks.append)
    assert "no node logs" in out.lower()
    assert chunks == [out]
