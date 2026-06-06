#!/usr/bin/env python3
"""Verify live database tables match the canonical dbSherpa schema (v5)."""
from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from runtime_env import ensure_env_loaded

ensure_env_loaded()

from app.database import get_connection  # noqa: E402

SCHEMA_VERSION = 5

EXPECTED_TABLES: dict[str, set[str]] = {
    "users": {
        "user_id", "username", "email", "name", "picture", "password_hash",
        "auth_provider", "role", "created_at", "last_login_at",
    },
    "user_sessions": {"session_token", "user_id", "expires_at", "created_at"},
    "workflows": {
        "user_id", "filename", "workflow_id", "name", "description", "workflow_data",
        "upvote_count", "downvote_count", "updated_at",
    },
    "drafts": {
        "user_id", "filename", "workflow_id", "name", "description", "workflow_data", "updated_at",
    },
    "workflow_votes": {"voter_user_id", "owner_user_id", "filename", "vote", "created_at"},
    "good_examples": {
        "id", "source_user_id", "source_filename", "workflow_id", "name", "description",
        "workflow_data", "promoted_at", "promote_to_folder", "promote_to_table", "folder_path",
    },
    "copilot_chats": {"session_id", "user_id", "title", "updated_at", "messages"},
    "user_memory": {"user_id", "content", "updated_at"},
    "user_skills": {"user_id", "skill_id", "is_owner", "created_at"},
    "user_data_source_access": {"user_id", "source_id", "has_access"},
    "user_preferences": {"user_id", "pref_key", "pref_value", "updated_at"},
    "user_feature_access": {"user_id", "feature_key", "enabled"},
    "run_logs": {
        "run_id", "user_id", "workflow", "started_at", "finished_at", "duration_ms", "status",
        "disposition", "node_count", "edge_count", "flag_count", "error", "report_path",
        "download_url", "run_log", "run_result", "run_error",
    },
    "run_artifacts": {
        "id", "run_id", "source_node_id", "file_name", "artifact_type", "file_path",
        "download_url", "generated_at",
    },
    "automations": {
        "id", "user_id", "name", "workflow_filename", "schedule_type", "cron_expression",
        "interval_mins", "duration_mins", "active", "author", "output_filename_pattern",
        "created_at", "updated_at",
    },
    "automation_runs": {
        "id", "automation_id", "run_id", "status", "triggered_at", "duration_ms", "error", "download_url",
    },
}


def _list_tables(cursor, db_type: str) -> set[str]:
    if db_type == "sqlite":
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row["name"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
    )
    return {row["TABLE_NAME"] for row in cursor.fetchall()}


def _list_columns(cursor, db_type: str, table: str) -> set[str]:
    if db_type == "sqlite":
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] if not isinstance(row, dict) else row["name"] for row in cursor.fetchall()}
    cursor.execute(
        """
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
        """,
        (table,),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def main() -> int:
    conn, db_type = get_connection()
    print(f"Database type: {db_type}")
    print(f"Expected schema version: {SCHEMA_VERSION}")
    ok = True

    try:
        cursor = conn.cursor()
        live_tables = _list_tables(cursor, db_type)
        expected_names = set(EXPECTED_TABLES)

        missing_tables = expected_names - live_tables
        extra_tables = live_tables - expected_names - {"sqlite_sequence"}

        if missing_tables:
            ok = False
            print("MISSING tables:", ", ".join(sorted(missing_tables)))
        if extra_tables:
            print("Extra tables (ignored):", ", ".join(sorted(extra_tables)))

        for table, expected_cols in sorted(EXPECTED_TABLES.items()):
            if table not in live_tables:
                continue
            cols = _list_columns(cursor, db_type, table)
            missing_cols = expected_cols - cols
            if missing_cols:
                ok = False
                print(f"MISSING columns on {table}: {', '.join(sorted(missing_cols))}")

        if ok:
            print(f"OK — all {len(EXPECTED_TABLES)} tables present with required columns.")
            return 0
        print("Schema verification FAILED.", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
