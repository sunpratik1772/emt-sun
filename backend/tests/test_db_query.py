"""db_query node — SQL LIMIT and SQLite execution."""
from __future__ import annotations

from engine.context import RunContext
from engine.nodes.db_query import run as db_query_run


def test_comms_messages_limit_20_via_sql() -> None:
    node = {
        "config": {
            "source": "comms_messages",
            "query": "SELECT * FROM comms_messages LIMIT 20",
        }
    }
    out = db_query_run(node, RunContext(), {})
    assert out["rowCount"] == 20
    assert len(out["rows"]) == 20


def test_comms_messages_without_limit_returns_full_fixture() -> None:
    node = {
        "config": {
            "source": "comms_messages",
            "query": "SELECT * FROM comms_messages",
        }
    }
    out = db_query_run(node, RunContext(), {})
    assert out["rowCount"] == 500


def test_limit_config_slices_oracle_source() -> None:
    node = {
        "config": {
            "source": "orders.csv",
            "query": "SELECT * FROM orders",
            "limit": 2,
        }
    }
    out = db_query_run(node, RunContext(), {})
    assert out["rowCount"] == 2
