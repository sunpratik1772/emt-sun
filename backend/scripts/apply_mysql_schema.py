#!/usr/bin/env python3
"""Apply backend/sql/001_schema_mysql.sql to the configured MySQL / Cloud SQL database."""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from runtime_env import ensure_env_loaded

ensure_env_loaded()

from app.database import get_connection  # noqa: E402


def _split_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def main() -> int:
    sql_path = backend_dir / "sql" / "001_schema_mysql.sql"
    if not sql_path.exists():
        print(f"Missing schema file: {sql_path}", file=sys.stderr)
        return 1

    conn, db_type = get_connection()
    if db_type != "mysql":
        print(
            "MySQL not configured. Set DATABASE_URL or MYSQL_HOST (+ user/password/database).",
            file=sys.stderr,
        )
        return 1

    sql = sql_path.read_text(encoding="utf-8")
    statements = _split_statements(sql)
    print(f"Applying {len(statements)} statements from {sql_path.name} ...")

    try:
        cursor = conn.cursor()
        for i, stmt in enumerate(statements, start=1):
            preview = stmt.split("\n", 1)[0][:80]
            print(f"  [{i}/{len(statements)}] {preview}")
            cursor.execute(stmt)
        conn.commit()
        print("MySQL schema applied successfully.")
        print("Next: start the API (init_db seeds John Doe) or run verify_schema.py")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"Schema apply failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
