"""Demo SQL fixture used by OracleConnector when ORACLE_DSN is unset."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "demo_data" / "surveillance_fixture.sqlite"

CORE_TABLES = ("hs_alerts", "hs_orders", "hs_exec", "hs_trades")
DEMO_TABLES = ("leads", "orders", "products")
ALL_TABLES = (*CORE_TABLES, "market_ticks", "comms_messages", *DEMO_TABLES)


def db_path(path: str | None = None) -> Path:
    if not path:
        return DEFAULT_DB_PATH
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (BACKEND_ROOT / candidate).resolve()


def ensure_fixture(path: str | None = None) -> Path:
    resolved = db_path(path)
    if resolved.exists():
        return resolved
    from scripts.gen_sqlite_demo_data import generate

    generate()
    return resolved


def fetch_table(table: str, *, path: str | None = None) -> list[dict[str, Any]]:
    if not table.isidentifier():
        raise ValueError(f"Invalid table name: {table!r}")
    resolved = ensure_fixture(path)
    with sqlite3.connect(resolved) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}").fetchall()]


def execute_select(sql: str, params: dict[str, Any] | None = None, *, path: str | None = None) -> list[dict[str, Any]]:
    resolved = ensure_fixture(path)
    with sqlite3.connect(resolved) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params or {}).fetchall()]


def table_counts(path: str | None = None) -> dict[str, int]:
    resolved = ensure_fixture(path)
    with sqlite3.connect(resolved) as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ALL_TABLES
        }


def list_tables(path: str | None = None) -> list[str]:
    resolved = ensure_fixture(path)
    with sqlite3.connect(resolved) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [str(row[0]) for row in rows]


def alert_payload(alert_id: str, *, path: str | None = None) -> dict[str, Any]:
    rows = execute_select(
        "SELECT * FROM hs_alerts WHERE alert_id = :alert_id",
        {"alert_id": alert_id},
        path=path,
    )
    if not rows:
        return {}
    row = rows[0]
    return {
        "alert_id": row["alert_id"],
        "participant_id": row["participant_id"],
        "trader_id": row["trader_id"],
        "trader_name": row["trader_name"],
        "keyword": row["keyword"],
        "date": row["alert_date"],
        "alert_date": row["alert_date"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "currency_pair": row["currency_pair"],
        "scenario": row["scenario"],
        "description": row["description"],
    }


def _context_from_filters(
    *,
    alert_id: str | None = None,
    participant_id: str | None = None,
    keyword: str | None = None,
    date: str | None = None,
    path: str | None = None,
    allow_participant: bool = True,
    allow_keyword: bool = True,
) -> dict[str, Any]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if alert_id:
        clauses.append("alert_id = :alert_id")
        params["alert_id"] = alert_id
    if allow_participant and participant_id:
        clauses.append("participant_id = :participant_id")
        params["participant_id"] = participant_id
    if allow_keyword and keyword:
        clauses.append("LOWER(keyword) LIKE LOWER(:keyword)")
        params["keyword"] = f"%{keyword}%"
    if date:
        clauses.append("alert_date = :date")
        params["date"] = date
    where = " AND ".join(clauses) if clauses else "1 = 1"
    rows = execute_select(
        f"SELECT * FROM hs_alerts WHERE {where} ORDER BY alert_id LIMIT 1",
        params,
        path=path,
    )
    return rows[0] if rows else {}


def query_core(
    table: str,
    *,
    alert_id: str | None = None,
    keyword: str | None = None,
    date: str | None = None,
    path: str | None = None,
) -> list[dict[str, Any]]:
    if table not in CORE_TABLES:
        raise ValueError(f"Unsupported core table: {table}")
    ctx = _context_from_filters(
        alert_id=alert_id,
        participant_id=None,
        keyword=keyword,
        date=date,
        path=path,
        allow_participant=False,
        allow_keyword=True,
    )
    if not ctx:
        return []
    sql = f"SELECT * FROM {table} WHERE alert_id = :alert_id"
    if table == "hs_alerts":
        sql = "SELECT * FROM hs_alerts WHERE alert_id = :alert_id"
    return execute_select(sql + " ORDER BY 1", {"alert_id": ctx["alert_id"]}, path=path)


def query_market(
    *,
    alert_id: str | None = None,
    keyword: str | None = None,
    date: str | None = None,
    currency_pair: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    source: str | None = None,
    query_type: str | None = None,
    path: str | None = None,
) -> list[dict[str, Any]]:
    ctx = _context_from_filters(
        alert_id=alert_id,
        participant_id=None,
        keyword=None,
        date=date,
        path=path,
        allow_participant=False,
        allow_keyword=False,
    )
    if not ctx:
        return []
    params: dict[str, Any] = {
        "alert_id": ctx["alert_id"],
        "currency_pair": currency_pair or ctx["currency_pair"],
        "start_time": start_time or ctx["start_time"],
        "end_time": end_time or ctx["end_time"],
    }
    sql = """
        SELECT * FROM market_ticks
        WHERE alert_id = :alert_id
          AND currency_pair = :currency_pair
          AND timestamp BETWEEN :start_time AND :end_time
        """
    if source:
        sql += " AND venue_name = :source"
        params["source"] = source
    if query_type:
        sql += " AND query_type = :query_type"
        params["query_type"] = query_type
    sql += " ORDER BY timestamp"
    return execute_select(sql, params, path=path)


def search_demo_data(
    *,
    alert_id: str | None = None,
    participant_id: str | None = None,
    keyword: str | None = None,
    date: str | None = None,
    path: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    ctx = _context_from_filters(
        alert_id=alert_id,
        participant_id=participant_id,
        keyword=keyword,
        date=date,
        path=path,
    )
    if not ctx:
        return {table: [] for table in ALL_TABLES}
    params = {"alert_id": ctx["alert_id"]}
    return {
        "hs_alerts": execute_select(
            "SELECT * FROM hs_alerts WHERE alert_id = :alert_id", params, path=path
        ),
        "hs_orders": execute_select(
            "SELECT * FROM hs_orders WHERE alert_id = :alert_id ORDER BY book, order_time",
            params,
            path=path,
        ),
        "hs_exec": execute_select(
            "SELECT * FROM hs_exec WHERE alert_id = :alert_id ORDER BY book, exec_time",
            params,
            path=path,
        ),
        "hs_trades": execute_select(
            "SELECT * FROM hs_trades WHERE alert_id = :alert_id ORDER BY book, trade_time",
            params,
            path=path,
        ),
        "market_ticks": query_market(alert_id=ctx["alert_id"], path=path),
        "comms_messages": execute_select(
            """
            SELECT * FROM comms_messages
            WHERE alert_id = :alert_id
            ORDER BY book, timestamp
            """,
            params,
            path=path,
        ),
    }
