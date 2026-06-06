"""Run/validate API profile for orchestrator workflows."""
from __future__ import annotations

from engine.copilot_validate import validate_dag_for_api


def test_orchestrator_trade_workflow_passes_api_validator() -> None:
    dag = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "n2",
                "type": "csv_extract",
                "label": "Trades",
                "config": {"source": "transactions.csv"},
            },
            {
                "id": "n3",
                "type": "agent",
                "label": "Score",
                "config": {"prompt": "x", "task": "y", "perRow": True},
            },
            {
                "id": "n4",
                "type": "csv_output",
                "label": "Report",
                "config": {"filename": "report.csv"},
            },
        ],
        "edges": [
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4"},
        ],
    }
    result = validate_dag_for_api(dag)
    assert result.valid, result.to_json()


def test_finalize_repairs_missing_last_edge() -> None:
    from copilot.orchestrator_pipeline import finalize_workflow

    wf = finalize_workflow(
        {
            "name": "Test",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "config": {}, "position": {"x": 60, "y": 0}},
                {"id": "n2", "type": "csv_extract", "config": {"source": "transactions.csv"}, "position": {"x": 300, "y": 0}},
                {"id": "n3", "type": "csv_output", "config": {"filename": "out.csv"}, "position": {"x": 600, "y": 0}},
            ],
            "edges": [{"source": "n1", "target": "n2"}],
        }
    )
    pairs = {(e["from"], e["to"]) for e in wf["edges"]}
    assert ("n2", "n3") in pairs
    assert validate_dag_for_api(wf).valid
