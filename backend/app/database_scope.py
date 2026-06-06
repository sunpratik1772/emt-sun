"""User-scoped schema migrations, seed data, votes, and access control tables."""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import bcrypt

from app.user_scope import (
    ROLE_ADMIN,
    ROLE_USER,
    SEED_EMAIL,
    SEED_NAME,
    SEED_PASSWORD,
    SEED_USER_ID,
    SEED_USERNAME,
    USER_FEATURES,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 5

PREF_GOOD_EXAMPLE_FOLDER = "good_example_promote_folder"
PREF_GOOD_EXAMPLE_TABLE = "good_example_promote_table"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _table_columns(cursor, db_type: str, table: str) -> set[str]:
    if db_type == "sqlite":
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] if not isinstance(row, dict) else row["name"] for row in cursor.fetchall()}
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table,),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def _ensure_column(cursor, db_type: str, table: str, column: str, sqlite_def: str, mysql_def: str) -> None:
    cols = _table_columns(cursor, db_type, table)
    if column in cols:
        return
    ddl = f"ALTER TABLE {table} ADD COLUMN {column} {sqlite_def if db_type == 'sqlite' else mysql_def}"
    cursor.execute(ddl)


def apply_user_scope_schema(cursor, db_type: str) -> None:
    """Create or migrate tables for per-user scoping."""
    if db_type == "sqlite":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data_source_access (
                user_id VARCHAR(255) NOT NULL,
                source_id VARCHAR(255) NOT NULL,
                has_access INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, source_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_skills (
                user_id VARCHAR(255) NOT NULL,
                skill_id VARCHAR(255) NOT NULL,
                is_owner INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                PRIMARY KEY (user_id, skill_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id VARCHAR(255) PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_votes (
                voter_user_id VARCHAR(255) NOT NULL,
                owner_user_id VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                vote VARCHAR(10) NOT NULL,
                created_at TEXT,
                PRIMARY KEY (voter_user_id, owner_user_id, filename)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS good_examples (
                id VARCHAR(255) PRIMARY KEY,
                source_user_id VARCHAR(255) NOT NULL,
                source_filename VARCHAR(255) NOT NULL,
                workflow_id VARCHAR(255),
                name VARCHAR(255),
                description TEXT,
                workflow_data TEXT NOT NULL,
                promoted_at TEXT,
                promote_to_folder INTEGER NOT NULL DEFAULT 1,
                promote_to_table INTEGER NOT NULL DEFAULT 1,
                folder_path TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id VARCHAR(255) NOT NULL,
                pref_key VARCHAR(255) NOT NULL,
                pref_value TEXT NOT NULL,
                updated_at TEXT,
                PRIMARY KEY (user_id, pref_key)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_feature_access (
                user_id VARCHAR(255) NOT NULL,
                feature_key VARCHAR(64) NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, feature_key)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data_source_access (
                user_id VARCHAR(255) NOT NULL,
                source_id VARCHAR(255) NOT NULL,
                has_access TINYINT NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, source_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_skills (
                user_id VARCHAR(255) NOT NULL,
                skill_id VARCHAR(255) NOT NULL,
                is_owner TINYINT NOT NULL DEFAULT 0,
                created_at DATETIME,
                PRIMARY KEY (user_id, skill_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_memory (
                user_id VARCHAR(255) PRIMARY KEY,
                content LONGTEXT NOT NULL,
                updated_at DATETIME
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_votes (
                voter_user_id VARCHAR(255) NOT NULL,
                owner_user_id VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                vote VARCHAR(10) NOT NULL,
                created_at DATETIME,
                PRIMARY KEY (voter_user_id, owner_user_id, filename)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS good_examples (
                id VARCHAR(255) PRIMARY KEY,
                source_user_id VARCHAR(255) NOT NULL,
                source_filename VARCHAR(255) NOT NULL,
                workflow_id VARCHAR(255),
                name VARCHAR(255),
                description TEXT,
                workflow_data LONGTEXT NOT NULL,
                promoted_at DATETIME,
                promote_to_folder TINYINT NOT NULL DEFAULT 1,
                promote_to_table TINYINT NOT NULL DEFAULT 1,
                folder_path VARCHAR(1000)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id VARCHAR(255) NOT NULL,
                pref_key VARCHAR(255) NOT NULL,
                pref_value TEXT NOT NULL,
                updated_at DATETIME,
                PRIMARY KEY (user_id, pref_key)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_feature_access (
                user_id VARCHAR(255) NOT NULL,
                feature_key VARCHAR(64) NOT NULL,
                enabled TINYINT NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, feature_key)
            )
        """)

    _ensure_column(cursor, db_type, "users", "username", "VARCHAR(255)", "VARCHAR(255)")
    _ensure_column(cursor, db_type, "users", "role", "VARCHAR(32) DEFAULT 'user'", "VARCHAR(32) DEFAULT 'user'")
    if db_type == "sqlite":
        cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (ROLE_ADMIN, SEED_USER_ID))
    else:
        cursor.execute("UPDATE users SET role = %s WHERE user_id = %s", (ROLE_ADMIN, SEED_USER_ID))
    _ensure_column(cursor, db_type, "workflows", "user_id", "VARCHAR(255)", "VARCHAR(255)")
    _ensure_column(cursor, db_type, "workflows", "upvote_count", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0")
    _ensure_column(cursor, db_type, "workflows", "downvote_count", "INTEGER DEFAULT 0", "INTEGER DEFAULT 0")
    _ensure_column(cursor, db_type, "drafts", "user_id", "VARCHAR(255)", "VARCHAR(255)")
    _ensure_column(cursor, db_type, "run_logs", "user_id", "VARCHAR(255)", "VARCHAR(255)")
    _ensure_column(cursor, db_type, "automations", "user_id", "VARCHAR(255)", "VARCHAR(255)")

    if db_type == "sqlite":
        cursor.execute("UPDATE workflows SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE drafts SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE run_logs SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE automations SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
    else:
        cursor.execute("UPDATE workflows SET user_id = %s WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE drafts SET user_id = %s WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE run_logs SET user_id = %s WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))
        cursor.execute("UPDATE automations SET user_id = %s WHERE user_id IS NULL OR user_id = ''", (SEED_USER_ID,))


def seed_default_user(cursor, db_type: str) -> None:
    """Ensure John Doe exists with username/password and default access grants."""
    if db_type == "sqlite":
        cursor.execute("SELECT user_id FROM users WHERE user_id = ? OR username = ? OR email = ?", (SEED_USER_ID, SEED_USERNAME, SEED_EMAIL))
    else:
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s OR username = %s OR email = %s", (SEED_USER_ID, SEED_USERNAME, SEED_EMAIL))
    row = cursor.fetchone()
    now = datetime.utcnow()
    now_val = now.isoformat() if db_type == "sqlite" else now
    if not row:
        password_hash = _hash_password(SEED_PASSWORD)
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT INTO users (user_id, username, email, name, picture, password_hash, auth_provider, role, created_at, last_login_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (SEED_USER_ID, SEED_USERNAME, SEED_EMAIL, SEED_NAME, None, password_hash, "email", ROLE_ADMIN, now_val, now_val),
            )
        else:
            cursor.execute(
                """
                INSERT INTO users (user_id, username, email, name, picture, password_hash, auth_provider, role, created_at, last_login_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (SEED_USER_ID, SEED_USERNAME, SEED_EMAIL, SEED_NAME, None, password_hash, "email", ROLE_ADMIN, now_val, now_val),
            )
    else:
        password_hash = _hash_password(SEED_PASSWORD)
        if db_type == "sqlite":
            cursor.execute(
                "UPDATE users SET username = ?, name = ?, email = ?, password_hash = ?, role = ? WHERE user_id = ?",
                (SEED_USERNAME, SEED_NAME, SEED_EMAIL, password_hash, ROLE_ADMIN, SEED_USER_ID),
            )
        else:
            cursor.execute(
                "UPDATE users SET username = %s, name = %s, email = %s, password_hash = %s, role = %s WHERE user_id = %s",
                (SEED_USERNAME, SEED_NAME, SEED_EMAIL, password_hash, ROLE_ADMIN, SEED_USER_ID),
            )

    _seed_user_data_sources(cursor, db_type, SEED_USER_ID)
    _seed_user_skills(cursor, db_type, SEED_USER_ID)


def _seed_user_data_sources(cursor, db_type: str, user_id: str) -> None:
    metadata_dir = Path(__file__).resolve().parent.parent / "connectors" / "metadata"
    if not metadata_dir.exists():
        return
    for path in sorted(metadata_dir.glob("*.yaml")):
        source_id = path.stem
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_data_source_access (user_id, source_id, has_access)
                VALUES (?, ?, 1)
                """,
                (user_id, source_id),
            )
        else:
            cursor.execute(
                """
                INSERT IGNORE INTO user_data_source_access (user_id, source_id, has_access)
                VALUES (%s, %s, 1)
                """,
                (user_id, source_id),
            )


def _seed_user_skills(cursor, db_type: str, user_id: str) -> None:
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    if not skills_dir.exists():
        return
    now = datetime.utcnow()
    now_val = now.isoformat() if db_type == "sqlite" else now
    for path in sorted(skills_dir.glob("skills-*.md")):
        skill_id = path.stem
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR IGNORE INTO user_skills (user_id, skill_id, is_owner, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (user_id, skill_id, now_val),
            )
        else:
            cursor.execute(
                """
                INSERT IGNORE INTO user_skills (user_id, skill_id, is_owner, created_at)
                VALUES (%s, %s, 0, %s)
                """,
                (user_id, skill_id, now_val),
            )


def get_user_by_username(username: str) -> dict | None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        else:
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_pref(user_id: str, pref_key: str, default: str | None = None) -> str | None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT pref_value FROM user_preferences WHERE user_id = ? AND pref_key = ?",
                (user_id, pref_key),
            )
        else:
            cursor.execute(
                "SELECT pref_value FROM user_preferences WHERE user_id = %s AND pref_key = %s",
                (user_id, pref_key),
            )
        row = cursor.fetchone()
        if not row:
            return default
        return str(row["pref_value"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()


def set_user_pref(user_id: str, pref_key: str, pref_value: str) -> None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        now_val = now.isoformat() if db_type == "sqlite" else now
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_preferences (user_id, pref_key, pref_value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, pref_key, pref_value, now_val),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO user_preferences (user_id, pref_key, pref_value, updated_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, pref_key, pref_value, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_good_example_promotion_prefs(user_id: str) -> dict[str, bool]:
    folder_default = _env_bool("DBSHERPA_GOOD_EXAMPLE_PROMOTE_FOLDER", True)
    table_default = _env_bool("DBSHERPA_GOOD_EXAMPLE_PROMOTE_TABLE", True)
    folder_raw = get_user_pref(user_id, PREF_GOOD_EXAMPLE_FOLDER)
    table_raw = get_user_pref(user_id, PREF_GOOD_EXAMPLE_TABLE)
    return {
        "promote_to_folder": folder_raw.strip().lower() in {"1", "true", "yes", "on"} if folder_raw else folder_default,
        "promote_to_table": table_raw.strip().lower() in {"1", "true", "yes", "on"} if table_raw else table_default,
    }


def set_good_example_promotion_prefs(
    user_id: str,
    *,
    promote_to_folder: bool | None = None,
    promote_to_table: bool | None = None,
) -> dict[str, bool]:
    if promote_to_folder is not None:
        set_user_pref(user_id, PREF_GOOD_EXAMPLE_FOLDER, "true" if promote_to_folder else "false")
    if promote_to_table is not None:
        set_user_pref(user_id, PREF_GOOD_EXAMPLE_TABLE, "true" if promote_to_table else "false")
    return get_good_example_promotion_prefs(user_id)


def list_data_source_access_rows(user_id: str) -> list[dict[str, Any]]:
    metadata_dir = Path(__file__).resolve().parent.parent / "connectors" / "metadata"
    allowed = set(list_accessible_data_source_ids(user_id))
    rows: list[dict[str, Any]] = []
    if not metadata_dir.exists():
        return rows
    import yaml

    for path in sorted(metadata_dir.glob("*.yaml")):
        source_id = path.stem
        doc: dict[str, Any] = {}
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
        rows.append({
            "source_id": source_id,
            "id": doc.get("id", source_id),
            "description": doc.get("description", ""),
            "has_access": source_id in allowed,
        })
    return rows


def set_data_source_access(user_id: str, source_id: str, has_access: bool) -> None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        access_int = 1 if has_access else 0
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_data_source_access (user_id, source_id, has_access)
                VALUES (?, ?, ?)
                """,
                (user_id, source_id, access_int),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO user_data_source_access (user_id, source_id, has_access)
                VALUES (%s, %s, %s)
                """,
                (user_id, source_id, access_int),
            )
        conn.commit()
    finally:
        conn.close()


def list_accessible_data_source_ids(user_id: str) -> list[str]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT source_id FROM user_data_source_access WHERE user_id = ? AND has_access = 1 ORDER BY source_id",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT source_id FROM user_data_source_access WHERE user_id = %s AND has_access = 1 ORDER BY source_id",
                (user_id,),
            )
        return [str(r["source_id"] if isinstance(r, dict) else r[0]) for r in cursor.fetchall()]
    finally:
        conn.close()


def list_accessible_skill_ids(user_id: str) -> list[str]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT skill_id FROM user_skills WHERE user_id = ? ORDER BY skill_id",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT skill_id FROM user_skills WHERE user_id = %s ORDER BY skill_id",
                (user_id,),
            )
        return [str(r["skill_id"] if isinstance(r, dict) else r[0]) for r in cursor.fetchall()]
    finally:
        conn.close()


def list_all_skill_ids() -> list[str]:
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    if not skills_dir.exists():
        return []
    return sorted(p.stem for p in skills_dir.glob("skills-*.md"))


def list_skill_access_rows(user_id: str) -> list[dict[str, Any]]:
    allowed = set(list_accessible_skill_ids(user_id))
    rows: list[dict[str, Any]] = []
    for skill_id in list_all_skill_ids():
        rows.append({
            "skill_id": skill_id,
            "id": skill_id,
            "has_access": skill_id in allowed,
        })
    return rows


def revoke_skill_from_user(user_id: str, skill_id: str) -> None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM user_skills WHERE user_id = ? AND skill_id = ?", (user_id, skill_id))
        else:
            cursor.execute("DELETE FROM user_skills WHERE user_id = %s AND skill_id = %s", (user_id, skill_id))
        conn.commit()
    finally:
        conn.close()


def set_skill_access(user_id: str, skill_id: str, has_access: bool) -> None:
    if has_access:
        grant_skill_to_user(user_id, skill_id)
    else:
        revoke_skill_from_user(user_id, skill_id)


def user_has_feature(user_id: str, feature_key: str) -> bool:
    key = (feature_key or "").strip()
    if key not in USER_FEATURES:
        return True
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT enabled FROM user_feature_access WHERE user_id = ? AND feature_key = ?",
                (user_id, key),
            )
        else:
            cursor.execute(
                "SELECT enabled FROM user_feature_access WHERE user_id = %s AND feature_key = %s",
                (user_id, key),
            )
        row = cursor.fetchone()
        if not row:
            return True
        val = row["enabled"] if isinstance(row, dict) else row[0]
        return bool(val)
    finally:
        conn.close()


def list_feature_access_rows(user_id: str) -> list[dict[str, Any]]:
    from app.database import get_connection

    disabled: set[str] = set()
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT feature_key FROM user_feature_access WHERE user_id = ? AND enabled = 0",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT feature_key FROM user_feature_access WHERE user_id = %s AND enabled = 0",
                (user_id,),
            )
        disabled = {str(r["feature_key"] if isinstance(r, dict) else r[0]) for r in cursor.fetchall()}
    finally:
        conn.close()

    return [
        {
            "feature_key": key,
            "label": label,
            "enabled": key not in disabled,
        }
        for key, label in USER_FEATURES.items()
    ]


def set_feature_access(user_id: str, feature_key: str, enabled: bool) -> None:
    key = (feature_key or "").strip()
    if key not in USER_FEATURES:
        raise ValueError(f"unknown feature: {key}")
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        enabled_int = 1 if enabled else 0
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_feature_access (user_id, feature_key, enabled)
                VALUES (?, ?, ?)
                """,
                (user_id, key, enabled_int),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO user_feature_access (user_id, feature_key, enabled)
                VALUES (%s, %s, %s)
                """,
                (user_id, key, enabled_int),
            )
        conn.commit()
    finally:
        conn.close()


def grant_skill_to_user(user_id: str, skill_id: str, *, is_owner: bool = False) -> None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        now_val = now.isoformat() if db_type == "sqlite" else now
        owner_int = 1 if is_owner else 0
        if db_type == "sqlite":
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_skills (user_id, skill_id, is_owner, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, skill_id, owner_int, now_val),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO user_skills (user_id, skill_id, is_owner, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, skill_id, owner_int, now_val),
            )
        conn.commit()
    finally:
        conn.close()


def get_user_memory_content(user_id: str) -> str:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("SELECT content FROM user_memory WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT content FROM user_memory WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            return ""
        return str(row["content"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()


def save_user_memory_content(user_id: str, content: str) -> None:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        now_val = now.isoformat() if db_type == "sqlite" else now
        if db_type == "sqlite":
            cursor.execute(
                "REPLACE INTO user_memory (user_id, content, updated_at) VALUES (?, ?, ?)",
                (user_id, content, now_val),
            )
        else:
            cursor.execute(
                "REPLACE INTO user_memory (user_id, content, updated_at) VALUES (%s, %s, %s)",
                (user_id, content, now_val),
            )
        conn.commit()
    finally:
        conn.close()


def cast_workflow_vote(
    voter_user_id: str,
    owner_user_id: str,
    filename: str,
    vote: str,
    *,
    good_examples_dir: Path | None = None,
    promote_to_folder: bool | None = None,
    promote_to_table: bool | None = None,
) -> dict[str, Any]:
    """Record upvote/downvote; upvotes promote workflow into good_examples table + folder."""
    from app.database import get_connection, get_workflow_db

    vote = vote.strip().lower()
    if vote not in {"up", "down"}:
        raise ValueError("vote must be 'up' or 'down'")

    row = get_workflow_db(filename, owner_user_id)
    if not row:
        raise LookupError(f"Workflow '{filename}' not found")

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        now_val = now.isoformat() if db_type == "sqlite" else now

        if db_type == "sqlite":
            cursor.execute(
                "SELECT vote FROM workflow_votes WHERE voter_user_id = ? AND owner_user_id = ? AND filename = ?",
                (voter_user_id, owner_user_id, filename),
            )
        else:
            cursor.execute(
                "SELECT vote FROM workflow_votes WHERE voter_user_id = %s AND owner_user_id = %s AND filename = %s",
                (voter_user_id, owner_user_id, filename),
            )
        prev = cursor.fetchone()
        prev_vote = str(prev["vote"] if isinstance(prev, dict) else prev[0]).lower() if prev else None

        if db_type == "sqlite":
            cursor.execute(
                """
                REPLACE INTO workflow_votes (voter_user_id, owner_user_id, filename, vote, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (voter_user_id, owner_user_id, filename, vote, now_val),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO workflow_votes (voter_user_id, owner_user_id, filename, vote, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (voter_user_id, owner_user_id, filename, vote, now_val),
            )

        up_delta = 0
        down_delta = 0
        if prev_vote == "up":
            up_delta -= 1
        elif prev_vote == "down":
            down_delta -= 1
        if vote == "up":
            up_delta += 1
        else:
            down_delta += 1

        if db_type == "sqlite":
            cursor.execute(
                """
                UPDATE workflows
                SET upvote_count = COALESCE(upvote_count, 0) + ?,
                    downvote_count = COALESCE(downvote_count, 0) + ?
                WHERE user_id = ? AND filename = ?
                """,
                (up_delta, down_delta, owner_user_id, filename),
            )
        else:
            cursor.execute(
                """
                UPDATE workflows
                SET upvote_count = COALESCE(upvote_count, 0) + %s,
                    downvote_count = COALESCE(downvote_count, 0) + %s
                WHERE user_id = %s AND filename = %s
                """,
                (up_delta, down_delta, owner_user_id, filename),
            )
        conn.commit()
    finally:
        conn.close()

    promoted: dict[str, Any] | None = None
    if vote == "up":
        prefs = get_good_example_promotion_prefs(voter_user_id)
        folder = promote_to_folder if promote_to_folder is not None else prefs["promote_to_folder"]
        table = promote_to_table if promote_to_table is not None else prefs["promote_to_table"]
        promoted = promote_workflow_to_good_examples(
            owner_user_id,
            filename,
            good_examples_dir=good_examples_dir,
            promote_to_folder=folder,
            promote_to_table=table,
        )

    updated = get_workflow_db(filename, owner_user_id) or {}
    return {
        "vote": vote,
        "previous_vote": prev_vote,
        "upvote_count": int(updated.get("upvote_count") or 0),
        "downvote_count": int(updated.get("downvote_count") or 0),
        "promoted": promoted,
    }


def promote_workflow_to_good_examples(
    owner_user_id: str,
    filename: str,
    *,
    good_examples_dir: Path | None = None,
    promote_to_folder: bool = True,
    promote_to_table: bool = True,
) -> dict[str, Any] | None:
    from app.database import get_connection, get_workflow_db
    from app.deps import GOOD_EXAMPLES_DIR

    row = get_workflow_db(filename, owner_user_id)
    if not row:
        return None

    dag_raw = row.get("workflow_data")
    dag = json.loads(dag_raw) if isinstance(dag_raw, str) else dag_raw
    if not isinstance(dag, dict):
        return None

    example_id = f"ge_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow()
    now_val = now.isoformat()
    folder_path: str | None = None

    target_dir = good_examples_dir or GOOD_EXAMPLES_DIR
    if promote_to_folder:
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(filename).stem
        if not stem.startswith("studio_"):
            stem = f"studio_upvoted_{stem}"
        out_name = f"{stem}.json"
        out_path = target_dir / out_name
        out_path.write_text(json.dumps(dag, indent=2), encoding="utf-8")
        folder_path = str(out_path)

    if promote_to_table:
        conn, db_type = get_connection()
        try:
            cursor = conn.cursor()
            folder_int = 1 if promote_to_folder else 0
            table_int = 1
            if db_type == "sqlite":
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO good_examples
                    (id, source_user_id, source_filename, workflow_id, name, description, workflow_data,
                     promoted_at, promote_to_folder, promote_to_table, folder_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        example_id,
                        owner_user_id,
                        filename,
                        row.get("workflow_id"),
                        row.get("name"),
                        row.get("description"),
                        json.dumps(dag),
                        now_val,
                        folder_int,
                        table_int,
                        folder_path,
                    ),
                )
            else:
                cursor.execute(
                    """
                    REPLACE INTO good_examples
                    (id, source_user_id, source_filename, workflow_id, name, description, workflow_data,
                     promoted_at, promote_to_folder, promote_to_table, folder_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        example_id,
                        owner_user_id,
                        filename,
                        row.get("workflow_id"),
                        row.get("name"),
                        row.get("description"),
                        json.dumps(dag),
                        now,
                        folder_int,
                        table_int,
                        folder_path,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    return {
        "id": example_id,
        "folder_path": folder_path,
        "promote_to_folder": promote_to_folder,
        "promote_to_table": promote_to_table,
    }


def list_good_examples_db() -> list[dict[str, Any]]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM good_examples ORDER BY promoted_at DESC")
        rows = cursor.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            row_dict = dict(r)
            promoted_at = row_dict.get("promoted_at")
            if isinstance(promoted_at, datetime):
                row_dict["promoted_at"] = promoted_at.isoformat()
            out.append(row_dict)
        return out
    finally:
        conn.close()


def list_public_users() -> list[dict[str, Any]]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username, email, name, role, created_at, last_login_at FROM users ORDER BY created_at ASC"
        )
        rows = cursor.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            row_dict = dict(r)
            for key in ("created_at", "last_login_at"):
                val = row_dict.get(key)
                if isinstance(val, datetime):
                    row_dict[key] = val.isoformat()
            row_dict["role"] = str(row_dict.get("role") or ROLE_USER).strip().lower()
            out.append(row_dict)
        return out
    finally:
        conn.close()


def set_user_role(user_id: str, role: str) -> dict[str, Any]:
    """Assign admin or user role to an existing account."""
    from app.database import get_connection, get_user_by_id

    normalized = (role or ROLE_USER).strip().lower()
    if normalized not in {ROLE_ADMIN, ROLE_USER}:
        raise ValueError("role must be 'admin' or 'user'")

    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("user not found")

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("UPDATE users SET role = ? WHERE user_id = ?", (normalized, user_id))
        else:
            cursor.execute("UPDATE users SET role = %s WHERE user_id = %s", (normalized, user_id))
        conn.commit()
    finally:
        conn.close()

    return {
        "user_id": user_id,
        "username": user.get("username"),
        "email": user.get("email"),
        "name": user.get("name"),
        "role": normalized,
    }


def delete_user_account(user_id: str) -> dict[str, Any]:
    """Remove a user account and all associated data."""
    from app.database import clear_all_workspace_data, get_connection, get_user_by_id

    target = (user_id or "").strip()
    if not target:
        raise ValueError("user_id is required")
    user = get_user_by_id(target)
    if not user:
        raise ValueError("user not found")

    deleted_workspace = clear_all_workspace_data(target)

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        extra_tables = (
            ("user_data_source_access", "user_id = ?"),
            ("user_preferences", "user_id = ?"),
            ("user_feature_access", "user_id = ?"),
            ("user_sessions", "user_id = ?"),
        )
        for table, where in extra_tables:
            if db_type == "sqlite":
                cursor.execute(f"DELETE FROM {table} WHERE {where}", (target,))
            else:
                cursor.execute(f"DELETE FROM {table} WHERE {where.replace('?', '%s')}", (target,))
            deleted_workspace[table] = cursor.rowcount if cursor.rowcount is not None else 0

        if db_type == "sqlite":
            cursor.execute("DELETE FROM users WHERE user_id = ?", (target,))
        else:
            cursor.execute("DELETE FROM users WHERE user_id = %s", (target,))
        if cursor.rowcount == 0:
            raise ValueError("user not found")
        conn.commit()
    finally:
        conn.close()

    return {
        "user_id": target,
        "username": user.get("username"),
        "deleted": deleted_workspace,
    }


def create_provisioned_user(
    *,
    first_name: str,
    last_name: str,
    username: str,
    password: str,
    data_source_access: dict[str, bool] | None = None,
    skill_access: dict[str, bool] | None = None,
    feature_access: dict[str, bool] | None = None,
    role: str = ROLE_USER,
) -> dict[str, Any]:
    """Create a user with optional connector, skill, and feature grants."""
    from app.database import get_connection, get_user_by_email, save_user

    username = username.strip().lower()
    first_name = first_name.strip()
    last_name = last_name.strip()
    name = f"{first_name} {last_name}".strip()
    email = f"{username}@dbsherpa.local"

    if not username:
        raise ValueError("username is required")
    if get_user_by_username(username):
        raise ValueError("username already taken")
    if get_user_by_email(email):
        raise ValueError("email already taken")

    normalized_role = (role or ROLE_USER).strip().lower()
    if normalized_role not in {ROLE_ADMIN, ROLE_USER}:
        raise ValueError("role must be 'admin' or 'user'")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    save_user(
        user_id=user_id,
        email=email,
        name=name,
        picture=None,
        password_hash=_hash_password(password),
        auth_provider="email",
        username=username,
        role=normalized_role,
    )

    for source_id, has_access in (data_source_access or {}).items():
        sid = (source_id or "").strip()
        if sid:
            set_data_source_access(user_id, sid, bool(has_access))

    if skill_access:
        for skill_id, has_access in skill_access.items():
            sid = (skill_id or "").strip()
            if sid and has_access:
                grant_skill_to_user(user_id, sid)
    else:
        conn, db_type = get_connection()
        try:
            cursor = conn.cursor()
            _seed_user_skills(cursor, db_type, user_id)
            conn.commit()
        finally:
            conn.close()

    for feature_key, enabled in (feature_access or {}).items():
        key = (feature_key or "").strip()
        if key in USER_FEATURES and not enabled:
            set_feature_access(user_id, key, False)

    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "name": name,
        "role": normalized_role,
    }


def _count_by_user(cursor, db_type: str, table: str) -> dict[str, int]:
    if db_type == "sqlite":
        cursor.execute(f"SELECT user_id, COUNT(*) AS c FROM {table} GROUP BY user_id")
    else:
        cursor.execute(f"SELECT user_id, COUNT(*) AS c FROM {table} GROUP BY user_id")
    out: dict[str, int] = {}
    for row in cursor.fetchall():
        row_dict = dict(row)
        uid = str(row_dict.get("user_id") or "").strip()
        if uid:
            out[uid] = int(row_dict.get("c") or 0)
    return out


def _list_all_workflows_summary() -> list[dict[str, Any]]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, filename, workflow_id, name, description, updated_at, upvote_count, downvote_count "
            "FROM workflows ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            row_dict = dict(r)
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                row_dict["updated_at"] = updated_at.isoformat()
            out.append({
                "user_id": row_dict.get("user_id"),
                "filename": row_dict.get("filename"),
                "workflow_id": row_dict.get("workflow_id"),
                "name": row_dict.get("name"),
                "description": row_dict.get("description"),
                "updated_at": str(row_dict.get("updated_at") or ""),
                "upvote_count": int(row_dict.get("upvote_count") or 0),
                "downvote_count": int(row_dict.get("downvote_count") or 0),
            })
        return out
    finally:
        conn.close()


def _list_all_drafts_summary() -> list[dict[str, Any]]:
    from app.database import get_connection

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, filename, workflow_id, name, description, updated_at "
            "FROM drafts ORDER BY updated_at DESC"
        )
        rows = cursor.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            row_dict = dict(r)
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                row_dict["updated_at"] = updated_at.isoformat()
            out.append({
                "user_id": row_dict.get("user_id"),
                "filename": row_dict.get("filename"),
                "workflow_id": row_dict.get("workflow_id"),
                "name": row_dict.get("name"),
                "description": row_dict.get("description"),
                "updated_at": str(row_dict.get("updated_at") or ""),
            })
        return out
    finally:
        conn.close()


def get_admin_overview(*, run_limit: int = 50) -> dict[str, Any]:
    """Platform-wide summary for the seed admin (John Doe)."""
    from app.database import get_connection, list_automations, list_db_run_logs

    users = list_public_users()
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        wf_counts = _count_by_user(cursor, db_type, "workflows")
        draft_counts = _count_by_user(cursor, db_type, "drafts")
        run_counts = _count_by_user(cursor, db_type, "run_logs")
        auto_counts = _count_by_user(cursor, db_type, "automations")
        chat_counts = _count_by_user(cursor, db_type, "copilot_chats")
    finally:
        conn.close()

    enriched_users: list[dict[str, Any]] = []
    for user in users:
        uid = str(user.get("user_id") or "")
        enriched_users.append({
            **user,
            "counts": {
                "workflows": wf_counts.get(uid, 0),
                "drafts": draft_counts.get(uid, 0),
                "runs": run_counts.get(uid, 0),
                "automations": auto_counts.get(uid, 0),
                "chats": chat_counts.get(uid, 0),
            },
        })

    workflows = _list_all_workflows_summary()
    drafts = _list_all_drafts_summary()
    runs = list_db_run_logs(limit=run_limit)
    automations_raw = list_automations(user_id=None)
    automations = [
        {
            "id": a.get("id"),
            "user_id": a.get("user_id"),
            "name": a.get("name"),
            "workflow_filename": a.get("workflow_filename"),
            "active": bool(a.get("active")),
            "schedule_type": a.get("schedule_type"),
            "created_at": a.get("created_at"),
        }
        for a in automations_raw
    ]

    runs_summary = [
        {
            "run_id": r.get("run_id"),
            "user_id": r.get("user_id"),
            "workflow": r.get("workflow"),
            "status": r.get("status"),
            "started_at": r.get("started_at"),
            "error": (r.get("error") or "")[:120] or None,
        }
        for r in runs
    ]

    return {
        "totals": {
            "users": len(users),
            "workflows": len(workflows),
            "drafts": len(drafts),
            "runs": sum(run_counts.values()),
            "automations": len(automations),
            "chats": sum(chat_counts.values()),
        },
        "users": enriched_users,
        "workflows": workflows,
        "drafts": drafts,
        "runs": runs_summary,
        "automations": automations,
        "skill_catalog": list_all_skill_ids(),
        "feature_catalog": [
            {"feature_key": key, "label": label}
            for key, label in USER_FEATURES.items()
        ],
    }
