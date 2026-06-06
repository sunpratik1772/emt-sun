"""Tests for join node left/right ordering and joinType fidelity."""
from __future__ import annotations

from engine.context import RunContext
from engine.join_utils import resolve_join_side_ids, run_join_rows
from engine.nodes.join import run as join_run


def _datasets() -> tuple[dict[str, Any], dict[str, Any]]:
    alerts = {
        "rows": [
            {"alert_id": "A1", "scenario": "spoofing"},
            {"alert_id": "A2", "scenario": "layering"},
        ],
    }
    comms = {
        "rows": [
            {"alert_id": "A1", "message_id": "M1"},
        ],
    }
    return alerts, comms


def test_resolve_join_side_ids_uses_target_handles() -> None:
    incoming = {"alerts": {}, "comms": {}}
    edges = [
        {"from": "comms", "to": "join", "targetHandle": "left"},
        {"from": "alerts", "to": "join", "targetHandle": "right"},
    ]
    left_id, right_id = resolve_join_side_ids("join", incoming, edges)
    assert left_id == "comms"
    assert right_id == "alerts"


def test_left_join_preserves_unmatched_left_rows() -> None:
    alerts, comms = _datasets()
    incoming = {"alerts": alerts, "comms": comms}
    edges = [
        {"from": "alerts", "to": "join", "targetHandle": "left"},
        {"from": "comms", "to": "join", "targetHandle": "right"},
    ]
    rows, meta = run_join_rows(
        "join",
        incoming,
        {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
        edges,
    )
    assert meta["joinType"] == "left"
    assert len(rows) == 2
    assert any(r.get("alert_id") == "A2" and "message_id" not in r for r in rows)


def test_join_run_echoes_configured_join_type_in_output() -> None:
    alerts, comms = _datasets()
    ctx = RunContext()
    ctx._active_edges = [
        {"from": "alerts", "to": "join", "targetHandle": "left"},
        {"from": "comms", "to": "join", "targetHandle": "right"},
    ]
    incoming = {"alerts": alerts, "comms": comms}
    out = join_run(
        {
            "id": "join",
            "type": "join",
            "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
        },
        ctx,
        incoming,
    )
    assert out["joinType"] == "left"
    assert out["left_source"] == "alerts"
    assert out["right_source"] == "comms"
