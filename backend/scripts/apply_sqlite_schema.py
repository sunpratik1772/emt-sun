#!/usr/bin/env python3
"""Apply backend/sql/002_schema_sqlite.sql then run init_db() for seed data."""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from runtime_env import ensure_env_loaded

ensure_env_loaded()

from app.database import get_connection, init_db  # noqa: E402


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.upper().startswith("PRAGMA"):
            if stripped.upper().startswith("PRAGMA"):
                statements.append(stripped.rstrip(";") + ";")
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
    return statements


def main() -> int:
    sql_path = backend_dir / "sql" / "002_schema_sqlite.sql"
    if not sql_path.exists():
        print(f"Missing schema file: {sql_path}", file=sys.stderr)
        return 1

    conn, db_type = get_connection()
    if db_type != "sqlite":
        print("SQLite expected (unset MYSQL_HOST / DATABASE_URL for local file DB).", file=sys.stderr)
        return 1

    sql = sql_path.read_text(encoding="utf-8")
    statements = _split_statements(sql)
    print(f"Applying {len(statements)} statements from {sql_path.name} ...")

    try:
        cursor = conn.cursor()
        for stmt in statements:
            cursor.execute(stmt)
        conn.commit()
    finally:
        conn.close()

    print("Running init_db() for migrations + seed user ...")
    init_db()
    print("SQLite schema ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
