"""Tests for in-memory dataset loading for Sherpa run analysis."""
from __future__ import annotations

from pathlib import Path

import pytest

from copilot.run_dataset_memory import (
    format_dataset_memory_markdown,
    load_run_dataset,
    replay_workflow_rows,
)

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


@pytest.mark.skipif(not _FIXTURE_DB.is_file(), reason="surveillance fixture missing")
def test_replay_comms_alerts_join_produces_500_rows() -> None:
    rows, source = replay_workflow_rows(_COMMS_ALERTS_WORKFLOW)
    assert "replayed" in source
    assert len(rows) == 500


_FRAUD_FILTER_WORKFLOW = {
    "nodes": [
        {"id": "n01", "type": "manual_trigger"},
        {
            "id": "n02",
            "type": "db_query",
            "config": {
                "source": "comms_messages",
                "query": (
                    "SELECT message_id, participant_id, display_post, keyword "
                    "FROM comms_messages"
                ),
            },
        },
        {
            "id": "n03",
            "type": "filter",
            "config": {"expression": "row.keyword === 'fixing'"},
        },
        {"id": "n04", "type": "csv_output", "config": {"filename": "fraud_comms_messages.csv"}},
    ],
    "edges": [
        {"from": "n01", "to": "n02"},
        {"from": "n02", "to": "n03"},
        {"from": "n03", "to": "n04"},
    ],
}


@pytest.mark.skipif(not _FIXTURE_DB.is_file(), reason="surveillance fixture missing")
def test_replay_filter_reduces_rows() -> None:
    rows, _source = replay_workflow_rows(_FRAUD_FILTER_WORKFLOW)
    assert len(rows) < 500
    assert all(r.get("keyword") == "fixing" for r in rows)


@pytest.mark.skipif(not _FIXTURE_DB.is_file(), reason="surveillance fixture missing")
def test_load_run_dataset_top_traders() -> None:
    memory = load_run_dataset(_COMMS_ALERTS_WORKFLOW, [], None)
    assert memory["row_count"] == 500
    top = memory["insights"]["top_traders_by_total_relevance"]
    assert len(top) >= 3
    assert top[0]["trader_name"] == "Riley Chen"
    md = format_dataset_memory_markdown(memory)
    assert "Riley Chen" in md
    assert "500" in md
