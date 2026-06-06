"""Tests for deterministic run verification facts and SQL."""
from __future__ import annotations

from copilot.llm_router import _heuristic_route
from copilot.run_verification import (
    build_verification_queries,
    compute_run_facts,
    infer_verification_plan,
    run_verification,
)


def _join_workflow() -> dict:
    return {
        "name": "Join Comms",
        "nodes": [
            {"id": "n02", "type": "db_query", "label": "Load Comms", "config": {}},
            {"id": "n03", "type": "db_query", "label": "Load Alerts", "config": {}},
            {
                "id": "n04",
                "type": "join",
                "label": "Join",
                "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
            },
        ],
        "edges": [],
    }


def _join_run_log(*, executed_join: str = "inner") -> list[dict]:
    rows = [
        {
            "alert_id": "A1",
            "scenario": "front_running",
            "message_id": "M1",
            "relevance_score": 0.9,
        },
        {
            "alert_id": "A2",
            "scenario": "spoofing",
            "message_id": "M2",
            "relevance_score": 0.8,
        },
    ]
    return [
        {
            "node_id": "n02",
            "node_type": "db_query",
            "label": "Load Comms",
            "status": "ok",
            "output": {"node_output": {"rowCount": 2, "rows": rows}},
        },
        {
            "node_id": "n04",
            "node_type": "join",
            "label": "Join",
            "status": "ok",
            "output": {
                "node_output": {
                    "rowCount": 2,
                    "rows": rows,
                    "joinType": executed_join,
                    "leftKey": "alert_id",
                    "rightKey": "alert_id",
                },
            },
        },
    ]


def test_compute_run_facts_detects_join_type_mismatch() -> None:
    facts = compute_run_facts(_join_workflow(), _join_run_log(executed_join="inner"))
    assert facts["joins"][0]["configured_join_type"] == "left"
    assert facts["joins"][0]["executed_join_type"] == "inner"
    assert facts["joins"][0]["join_type_mismatch"] is True


def test_infer_verification_plan_for_reliability_message() -> None:
    plan = infer_verification_plan(
        "Review the latest run and suggest one change to improve reliability.",
        {"wants_sql": True},
    )
    assert "row_counts" in plan
    assert "join_orphans" in plan


def test_build_verification_queries_uses_alert_side_orphan_column() -> None:
    queries = build_verification_queries(
        ["join_orphans"],
        ["alert_id", "scenario", "message_id"],
    )
    assert len(queries) == 1
    assert "scenario" in queries[0]["sql"]
    assert "alert_id IS NULL" not in queries[0]["sql"]


def test_run_verification_executes_orphan_check() -> None:
    verification = run_verification(
        _join_workflow(),
        _join_run_log(),
        None,
        user_message="suggest one change to improve reliability",
        route_metadata={"verification_plan": ["row_counts", "join_orphans"]},
    )
    assert verification["verification_summary"]["total_rows"] == 2
    assert verification["verification_summary"]["orphan_rows"] == 0
    assert verification["verification_summary"]["suggest_left_join"] is False


def test_heuristic_improve_with_failures_routes_build_not_explain_error() -> None:
    msg = (
        'Improve "Join Comms" with validation, a branch for failures, '
        "and an Outlook summary when the run completes."
    )
    route = _heuristic_route(msg, has_workflow=True, has_run_log=False)
    assert route.intent == "build"
