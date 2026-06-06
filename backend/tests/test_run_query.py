"""Deterministic tests for run output SQL query."""
from __future__ import annotations

from app.run_query import execute_run_query, materialize_run_rows


def test_execute_run_query_groups_rows() -> None:
    rows = [
        {"trader_name": "Alice", "relevance_score": "0.9"},
        {"trader_name": "Bob", "relevance_score": "0.5"},
        {"trader_name": "Alice", "relevance_score": "0.8"},
    ]
    result = execute_run_query(
        rows,
        "SELECT trader_name, COUNT(*) AS n FROM run_output GROUP BY trader_name ORDER BY n DESC",
    )
    assert result["row_count"] == 2
    assert result["columns"] == ["trader_name", "n"]
    alice = next(r for r in result["rows"] if r["trader_name"] == "Alice")
    assert str(alice["n"]) == "2"


def test_execute_run_query_rejects_non_select() -> None:
    try:
        execute_run_query([{"a": "1"}], "DELETE FROM run_output")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SELECT" in str(exc)


def test_materialize_from_run_log_rows() -> None:
    run_row = {
        "workflow": "Test WF",
        "run_log": [
            {
                "output": {
                    "node_output": {
                        "rows": [{"x": "1"}, {"x": "2"}],
                    },
                },
            },
        ],
        "artifacts": [],
    }
    rows, source = materialize_run_rows(run_row, None)
    assert len(rows) == 2
    assert source == "run_log"
