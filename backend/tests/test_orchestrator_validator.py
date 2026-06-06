"""Copilot Layer 4a — orchestrator-backend validator parity."""
from __future__ import annotations

from copilot.orchestrator_validator import validate_dag, validate_workflow


def test_manual_trigger_not_flagged_as_orphan() -> None:
    """Orchestrator validator does not require incoming edges on triggers."""
    err = validate_dag(
        [
            {"id": "n1", "type": "manual_trigger", "config": {}},
            {"id": "n2", "type": "csv_extract", "config": {"source": "transactions.csv"}},
        ],
        [{"source": "n1", "target": "n2"}],
    )
    assert err is None


def test_agent_aggregate_skips_per_row_fields() -> None:
    err = validate_dag(
        [
            {"id": "n1", "type": "manual_trigger", "config": {}},
            {"id": "n3", "type": "agent", "config": {"prompt": "x", "task": "y"}},
        ],
        [{"from": "n1", "to": "n3"}],
    )
    assert err is None


def test_agent_per_row_applies_defaults() -> None:
    err = validate_dag(
        [
            {"id": "n1", "type": "manual_trigger", "config": {}},
            {"id": "n3", "type": "agent", "config": {"perRow": True, "prompt": "x", "task": "y"}},
        ],
        [{"source": "n1", "target": "n3"}],
    )
    assert err is None


def test_condition_requires_source_handle() -> None:
    err = validate_dag(
        [
            {"id": "n1", "type": "manual_trigger", "config": {}},
            {"id": "c1", "type": "condition", "config": {"expression": "row.x > 1"}},
            {"id": "n2", "type": "filter", "config": {"expression": "true"}},
        ],
        [
            {"source": "n1", "target": "c1"},
            {"source": "c1", "target": "n2"},
        ],
    )
    assert err is not None
    assert "sourceHandle" in err


def test_orphan_non_entry_rejected() -> None:
    err = validate_dag(
        [
            {"id": "n1", "type": "manual_trigger", "config": {}},
            {"id": "n2", "type": "csv_extract", "config": {"source": "transactions.csv"}},
            {"id": "n3", "type": "csv_output", "config": {"filename": "out.csv"}},
        ],
        [{"source": "n1", "target": "n2"}],
    )
    assert err is not None
    assert "no incoming edge" in err
    assert "n3" in err


def test_unknown_type_rejected() -> None:
    err = validate_workflow(
        {
            "nodes": [{"id": "n1", "type": "not_a_real_node", "config": {}}],
            "edges": [],
        }
    )
    assert err is not None
    assert "unknown type" in err
