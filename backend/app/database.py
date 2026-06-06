from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
SQLITE_DB_PATH = BACKEND_DIR / "copilot_chats.db"


def get_connection():
    """Resolves and returns a database connection + connection type (sqlite or mysql)."""
    db_url = os.environ.get("DATABASE_URL", "")
    mysql_host = os.environ.get("MYSQL_HOST") or os.environ.get("DB_HOST")

    if db_url.startswith("mysql") or mysql_host:
        try:
            import pymysql

            if db_url.startswith("mysql"):
                # Parse URL format: mysql://user:password@host:port/db_name
                # or mysql+pymysql://user:password@host:port/db_name
                url = db_url.split("://", 1)[1]
                auth_part, host_part = url.split("@", 1)
                user, password = auth_part.split(":", 1)
                host_db = host_part.split("/", 1)
                host_port = host_db[0].split(":", 1)
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 3306
                db = host_db[1] if len(host_db) > 1 else "dbsherpa"
            else:
                host = mysql_host
                user = os.environ.get("MYSQL_USER") or os.environ.get("DB_USER", "root")
                password = os.environ.get("MYSQL_PASSWORD") or os.environ.get("DB_PASSWORD", "")
                db = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME", "dbsherpa")
                port = int(os.environ.get("MYSQL_PORT") or os.environ.get("DB_PORT", 3306))

            unix_socket = os.environ.get("MYSQL_UNIX_SOCKET") or os.environ.get("CLOUD_SQL_UNIX_SOCKET")
            connect_kwargs: dict = {
                "user": user,
                "password": password,
                "database": db,
                "cursorclass": pymysql.cursors.DictCursor,
            }
            if unix_socket:
                connect_kwargs["unix_socket"] = unix_socket
            else:
                connect_kwargs["host"] = host
                connect_kwargs["port"] = port

            conn = pymysql.connect(**connect_kwargs)
            return conn, "mysql"
        except ImportError:
            logger.error("pymysql is required for MySQL support but not installed. Falling back to SQLite.")
        except Exception as e:
            logger.error(f"Failed to connect to MySQL database: {e}. Falling back to SQLite.")

    # SQLite fallback
    import sqlite3

    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def init_db():
    """Initializes the database schema if the table does not exist."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copilot_chats (
                    session_id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    title VARCHAR(255),
                    updated_at TEXT,
                    messages TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_logs (
                    run_id VARCHAR(255) PRIMARY KEY,
                    workflow VARCHAR(255),
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    status VARCHAR(50),
                    disposition VARCHAR(255),
                    node_count INTEGER,
                    edge_count INTEGER,
                    flag_count INTEGER,
                    error TEXT,
                    report_path TEXT,
                    download_url TEXT,
                    run_log TEXT,
                    run_result TEXT,
                    run_error TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(255) NOT NULL,
                    source_node_id VARCHAR(255),
                    file_name VARCHAR(500),
                    artifact_type VARCHAR(50),
                    file_path TEXT,
                    download_url TEXT,
                    generated_at TEXT,
                    UNIQUE(run_id, source_node_id, file_name, download_url)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    name VARCHAR(255),
                    picture VARCHAR(255),
                    password_hash VARCHAR(255),
                    auth_provider VARCHAR(50),
                    created_at TEXT,
                    last_login_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_token VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    expires_at TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automations (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255),
                    workflow_filename VARCHAR(255),
                    schedule_type VARCHAR(50),
                    cron_expression VARCHAR(255),
                    interval_mins INTEGER,
                    duration_mins INTEGER,
                    active INTEGER,
                    author VARCHAR(255),
                    output_filename_pattern TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id VARCHAR(255) PRIMARY KEY,
                    automation_id VARCHAR(255),
                    run_id VARCHAR(255),
                    status VARCHAR(50),
                    triggered_at TEXT,
                    duration_ms INTEGER,
                    error TEXT,
                    download_url TEXT,
                    FOREIGN KEY(automation_id) REFERENCES automations(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    user_id VARCHAR(255) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    workflow_id VARCHAR(255),
                    name VARCHAR(255),
                    description TEXT,
                    workflow_data TEXT,
                    upvote_count INTEGER DEFAULT 0,
                    downvote_count INTEGER DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (user_id, filename)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    user_id VARCHAR(255) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    workflow_id VARCHAR(255),
                    name VARCHAR(255),
                    description TEXT,
                    workflow_data TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (user_id, filename)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copilot_chats (
                    session_id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    title VARCHAR(255),
                    updated_at DATETIME,
                    messages LONGTEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_logs (
                    run_id VARCHAR(255) PRIMARY KEY,
                    workflow VARCHAR(255),
                    started_at VARCHAR(255),
                    finished_at VARCHAR(255),
                    duration_ms INTEGER,
                    status VARCHAR(50),
                    disposition VARCHAR(255),
                    node_count INTEGER,
                    edge_count INTEGER,
                    flag_count INTEGER,
                    error TEXT,
                    report_path VARCHAR(500),
                    download_url VARCHAR(500),
                    run_log LONGTEXT,
                    run_result LONGTEXT,
                    run_error TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    run_id VARCHAR(255) NOT NULL,
                    source_node_id VARCHAR(255),
                    file_name VARCHAR(500),
                    artifact_type VARCHAR(50),
                    file_path VARCHAR(1000),
                    download_url VARCHAR(1000),
                    generated_at VARCHAR(255),
                    UNIQUE KEY uniq_run_artifact (run_id, source_node_id, file_name, download_url)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE,
                    name VARCHAR(255),
                    picture VARCHAR(255),
                    password_hash VARCHAR(255),
                    auth_provider VARCHAR(50),
                    created_at DATETIME,
                    last_login_at DATETIME
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_token VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    expires_at DATETIME,
                    created_at DATETIME
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automations (
                    id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255),
                    workflow_filename VARCHAR(255),
                    schedule_type VARCHAR(50),
                    cron_expression VARCHAR(255),
                    interval_mins INTEGER,
                    duration_mins INTEGER,
                    active INTEGER,
                    author VARCHAR(255),
                    output_filename_pattern VARCHAR(500),
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS automation_runs (
                    id VARCHAR(255) PRIMARY KEY,
                    automation_id VARCHAR(255),
                    run_id VARCHAR(255),
                    status VARCHAR(50),
                    triggered_at DATETIME,
                    duration_ms INTEGER,
                    error TEXT,
                    download_url VARCHAR(500),
                    FOREIGN KEY(automation_id) REFERENCES automations(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    user_id VARCHAR(255) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    workflow_id VARCHAR(255),
                    name VARCHAR(255),
                    description TEXT,
                    workflow_data LONGTEXT,
                    upvote_count INTEGER DEFAULT 0,
                    downvote_count INTEGER DEFAULT 0,
                    updated_at DATETIME,
                    PRIMARY KEY (user_id, filename)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    user_id VARCHAR(255) NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    workflow_id VARCHAR(255),
                    name VARCHAR(255),
                    description TEXT,
                    workflow_data LONGTEXT,
                    updated_at DATETIME,
                    PRIMARY KEY (user_id, filename)
                )
            """)
        # Migration: Add download_url column if not exists
        try:
            if db_type == "sqlite":
                cursor.execute("ALTER TABLE automation_runs ADD COLUMN download_url TEXT")
            else:
                cursor.execute("ALTER TABLE automation_runs ADD COLUMN download_url VARCHAR(500)")
        except Exception:
            pass

        # Migration: Add output_filename_pattern column if not exists
        try:
            if db_type == "sqlite":
                cursor.execute("ALTER TABLE automations ADD COLUMN output_filename_pattern TEXT")
            else:
                cursor.execute("ALTER TABLE automations ADD COLUMN output_filename_pattern VARCHAR(500)")
        except Exception:
            pass

        # Migration: run payload columns for full output-panel history
        for column_name, sqlite_col, mysql_col in (
            ("run_log", "TEXT", "LONGTEXT"),
            ("run_result", "TEXT", "LONGTEXT"),
            ("run_error", "TEXT", "TEXT"),
        ):
            try:
                if db_type == "sqlite":
                    cursor.execute(f"ALTER TABLE run_logs ADD COLUMN {column_name} {sqlite_col}")
                else:
                    cursor.execute(f"ALTER TABLE run_logs ADD COLUMN {column_name} {mysql_col}")
            except Exception:
                pass

        if db_type == "sqlite":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id VARCHAR(255) NOT NULL,
                    source_node_id VARCHAR(255),
                    file_name VARCHAR(500),
                    artifact_type VARCHAR(50),
                    file_path TEXT,
                    download_url TEXT,
                    generated_at TEXT,
                    UNIQUE(run_id, source_node_id, file_name, download_url)
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id BIGINT PRIMARY KEY AUTO_INCREMENT,
                    run_id VARCHAR(255) NOT NULL,
                    source_node_id VARCHAR(255),
                    file_name VARCHAR(500),
                    artifact_type VARCHAR(50),
                    file_path VARCHAR(1000),
                    download_url VARCHAR(1000),
                    generated_at VARCHAR(255),
                    UNIQUE KEY uniq_run_artifact (run_id, source_node_id, file_name, download_url)
                )
            """)

        from app.user_scope import SEED_USER_ID

        # Seeding logic for workflows table
        try:
            cursor.execute("SELECT COUNT(*) as count FROM workflows")
            row = cursor.fetchone()
            count = row["count"] if row else 0
            if count == 0:
                workflows_dir = Path(os.environ.get("DBSHERPA_WORKFLOWS_DIR", str(BACKEND_DIR / "workflows")))
                if workflows_dir.exists():
                    import yaml
                    for f in workflows_dir.iterdir():
                        if f.is_file() and f.suffix in {".json", ".yaml", ".yml"}:
                            if f.name.startswith("studio_"):
                                continue
                            try:
                                text = f.read_text(encoding="utf-8")
                                if f.suffix == ".json":
                                    dag = json.loads(text)
                                else:
                                    dag = yaml.safe_load(text)
                                
                                if not isinstance(dag, dict):
                                    continue
                                
                                workflow_id = dag.get("workflow_id")
                                name = dag.get("name") or f.name
                                description = dag.get("description")
                                workflow_data = json.dumps(dag)
                                stat = f.stat()
                                mtime = datetime.utcfromtimestamp(stat.st_mtime)
                                
                                if db_type == "sqlite":
                                    cursor.execute(
                                        "INSERT INTO workflows (user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)",
                                        (SEED_USER_ID, f.name, workflow_id, name, description, workflow_data, mtime.isoformat())
                                    )
                                else:
                                    cursor.execute(
                                        "INSERT INTO workflows (user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0)",
                                        (SEED_USER_ID, f.name, workflow_id, name, description, workflow_data, mtime)
                                    )
                            except Exception as exc:
                                logger.error(f"Error seeding workflow {f.name}: {exc}")
        except Exception as e:
            logger.error(f"Failed to seed workflows: {e}")

        # Import legacy drafts/ files when drafts table is empty
        try:
            cursor.execute("SELECT COUNT(*) as count FROM drafts")
            row = cursor.fetchone()
            draft_count = row["count"] if row else 0
            if draft_count == 0:
                drafts_dir = Path(os.environ.get("DBSHERPA_DRAFTS_DIR", str(BACKEND_DIR / "drafts")))
                if drafts_dir.exists():
                    for f in drafts_dir.iterdir():
                        if not f.is_file() or f.suffix not in {".json", ".yaml", ".yml"}:
                            continue
                        try:
                            text = f.read_text(encoding="utf-8")
                            if f.suffix == ".json":
                                dag = json.loads(text)
                            else:
                                import yaml
                                dag = yaml.safe_load(text)
                            if not isinstance(dag, dict):
                                continue
                            stat = f.stat()
                            mtime = datetime.utcfromtimestamp(stat.st_mtime)
                            payload = (
                                SEED_USER_ID,
                                f.name,
                                dag.get("workflow_id"),
                                dag.get("name") or f.name,
                                dag.get("description"),
                                json.dumps(dag),
                                mtime.isoformat() if db_type == "sqlite" else mtime,
                            )
                            if db_type == "sqlite":
                                cursor.execute(
                                    "INSERT INTO drafts (user_id, filename, workflow_id, name, description, workflow_data, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    payload,
                                )
                            else:
                                cursor.execute(
                                    "INSERT INTO drafts (user_id, filename, workflow_id, name, description, workflow_data, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                    payload,
                                )
                        except Exception as exc:
                            logger.error(f"Error importing draft {f.name}: {exc}")
        except Exception as e:
            logger.error(f"Failed to seed drafts: {e}")

        # Import legacy user workflow files into DB when missing (one row per filename)
        try:
            workflows_dir = Path(os.environ.get("DBSHERPA_WORKFLOWS_DIR", str(BACKEND_DIR / "workflows")))
            if workflows_dir.exists():
                import yaml
                for f in workflows_dir.iterdir():
                    if not f.is_file() or f.suffix not in {".json", ".yaml", ".yml"}:
                        continue
                    if f.name.startswith("studio_"):
                        continue
                    if get_workflow_db(f.name, SEED_USER_ID):
                        continue
                    try:
                        text = f.read_text(encoding="utf-8")
                        dag = json.loads(text) if f.suffix == ".json" else yaml.safe_load(text)
                        if not isinstance(dag, dict):
                            continue
                        stat = f.stat()
                        mtime = datetime.utcfromtimestamp(stat.st_mtime)
                        save_workflow_db(
                            filename=f.name,
                            workflow_id=dag.get("workflow_id"),
                            name=dag.get("name") or f.name,
                            description=dag.get("description"),
                            workflow_data=json.dumps(dag),
                            user_id=SEED_USER_ID,
                            mtime=mtime,
                        )
                    except Exception as exc:
                        logger.error(f"Error importing legacy workflow {f.name}: {exc}")
        except Exception as e:
            logger.error(f"Failed to import legacy workflows: {e}")

        from app.database_scope import apply_user_scope_schema, seed_default_user

        apply_user_scope_schema(cursor, db_type)
        seed_default_user(cursor, db_type)

        conn.commit()
    finally:
        conn.close()


def save_draft_db(
    filename: str,
    workflow_id: str | None,
    name: str | None,
    description: str | None,
    workflow_data: str,
    user_id: str,
    mtime: datetime | None = None,
) -> None:
    """Saves or updates a draft workflow in the database."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = mtime or datetime.utcnow()
        if db_type == "sqlite":
            cursor.execute(
                "REPLACE INTO drafts (user_id, filename, workflow_id, name, description, workflow_data, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, filename, workflow_id, name, description, workflow_data, now.isoformat()),
            )
        else:
            cursor.execute(
                "REPLACE INTO drafts (user_id, filename, workflow_id, name, description, workflow_data, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (user_id, filename, workflow_id, name, description, workflow_data, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_draft_db(filename: str, user_id: str) -> dict | None:
    """Retrieves a single draft by filename."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at FROM drafts WHERE user_id = ? AND filename = ?",
                (user_id, filename),
            )
        else:
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at FROM drafts WHERE user_id = %s AND filename = %s",
                (user_id, filename),
            )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_draft_db(filename: str, user_id: str) -> None:
    """Deletes a draft from the database."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM drafts WHERE user_id = ? AND filename = ?", (user_id, filename))
        else:
            cursor.execute("DELETE FROM drafts WHERE user_id = %s AND filename = %s", (user_id, filename))
        conn.commit()
    finally:
        conn.close()


def list_drafts_db(user_id: str) -> list[dict]:
    """Lists draft workflows owned by a user."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at FROM drafts WHERE user_id = ?",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at FROM drafts WHERE user_id = %s",
                (user_id,),
            )
        rows = cursor.fetchall()
        out = []
        for r in rows:
            row_dict = dict(r)
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                updated_at = updated_at.isoformat()
            out.append({
                "user_id": row_dict.get("user_id"),
                "filename": row_dict.get("filename"),
                "workflow_id": row_dict.get("workflow_id"),
                "name": row_dict.get("name"),
                "description": row_dict.get("description"),
                "workflow_data": row_dict.get("workflow_data"),
                "updated_at": str(updated_at) if updated_at else None,
            })
        return out
    finally:
        conn.close()


def save_workflow_db(
    filename: str,
    workflow_id: str | None,
    name: str | None,
    description: str | None,
    workflow_data: str,
    user_id: str,
    mtime: datetime | None = None,
):
    """Saves or updates a workflow configuration in the database."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = mtime or datetime.utcnow()
        if db_type == "sqlite":
            cursor.execute(
                """
                REPLACE INTO workflows
                (user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT upvote_count FROM workflows WHERE user_id = ? AND filename = ?), 0),
                        COALESCE((SELECT downvote_count FROM workflows WHERE user_id = ? AND filename = ?), 0))
                """,
                (
                    user_id,
                    filename,
                    workflow_id,
                    name,
                    description,
                    workflow_data,
                    now.isoformat(),
                    user_id,
                    filename,
                    user_id,
                    filename,
                ),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO workflows
                (user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        COALESCE((SELECT upvote_count FROM workflows w WHERE w.user_id = %s AND w.filename = %s), 0),
                        COALESCE((SELECT downvote_count FROM workflows w WHERE w.user_id = %s AND w.filename = %s), 0))
                """,
                (
                    user_id,
                    filename,
                    workflow_id,
                    name,
                    description,
                    workflow_data,
                    now,
                    user_id,
                    filename,
                    user_id,
                    filename,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_workflow_db(filename: str, user_id: str) -> dict | None:
    """Retrieves a single workflow configuration by filename."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count FROM workflows WHERE user_id = ? AND filename = ?",
                (user_id, filename),
            )
        else:
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count FROM workflows WHERE user_id = %s AND filename = %s",
                (user_id, filename),
            )
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def delete_workflow_db(filename: str, user_id: str):
    """Deletes a workflow configuration from the database."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM workflows WHERE user_id = ? AND filename = ?", (user_id, filename))
        else:
            cursor.execute("DELETE FROM workflows WHERE user_id = %s AND filename = %s", (user_id, filename))
        conn.commit()
    finally:
        conn.close()


def list_workflows_db(user_id: str) -> list[dict]:
    """Lists stored workflow configurations owned by a user."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count FROM workflows WHERE user_id = ?",
                (user_id,),
            )
        else:
            cursor.execute(
                "SELECT user_id, filename, workflow_id, name, description, workflow_data, updated_at, upvote_count, downvote_count FROM workflows WHERE user_id = %s",
                (user_id,),
            )
        rows = cursor.fetchall()
        out = []
        for r in rows:
            row_dict = dict(r)
            updated_at = row_dict.get("updated_at")
            if isinstance(updated_at, datetime):
                updated_at = updated_at.isoformat()
            out.append({
                "user_id": row_dict.get("user_id"),
                "filename": row_dict.get("filename"),
                "workflow_id": row_dict.get("workflow_id"),
                "name": row_dict.get("name"),
                "description": row_dict.get("description"),
                "workflow_data": row_dict.get("workflow_data"),
                "upvote_count": int(row_dict.get("upvote_count") or 0),
                "downvote_count": int(row_dict.get("downvote_count") or 0),
                "updated_at": str(updated_at) if updated_at else None,
            })
        return out
    finally:
        conn.close()


def list_chats(user_id: str) -> list[dict]:
    """Retrieves all past chats for a user, sorted by updated_at descending."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT session_id, title, updated_at FROM copilot_chats WHERE user_id = ? ORDER BY updated_at DESC LIMIT 100",
                (user_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "session_id": r["session_id"],
                    "title": r["title"] or "New Chat",
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        else:
            cursor.execute(
                "SELECT session_id, title, updated_at FROM copilot_chats WHERE user_id = %s ORDER BY updated_at DESC LIMIT 100",
                (user_id,),
            )
            rows = cursor.fetchall()
            formatted = []
            for r in rows:
                updated_at = r["updated_at"]
                if isinstance(updated_at, datetime):
                    updated_at = updated_at.isoformat()
                formatted.append({
                    "session_id": r["session_id"],
                    "title": r["title"] or "New Chat",
                    "updated_at": str(updated_at),
                })
            return formatted
    finally:
        conn.close()


def get_chat(session_id: str, user_id: str) -> dict | None:
    """Retrieves a single chat session."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT session_id, user_id, title, messages FROM copilot_chats WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            )
            row = cursor.fetchone()
        else:
            cursor.execute(
                "SELECT session_id, user_id, title, messages FROM copilot_chats WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
            row = cursor.fetchone()

        if not row:
            return None

        try:
            messages = json.loads(row["messages"])
        except Exception:
            messages = []

        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "messages": messages,
        }
    finally:
        conn.close()


def save_chat(session_id: str, user_id: str, title: str, messages: list[dict]):
    """Saves or updates a chat session."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        messages_str = json.dumps(messages)

        if db_type == "sqlite":
            cursor.execute(
                "REPLACE INTO copilot_chats (session_id, user_id, title, updated_at, messages) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, title, now.isoformat(), messages_str),
            )
        else:
            cursor.execute(
                "REPLACE INTO copilot_chats (session_id, user_id, title, updated_at, messages) VALUES (%s, %s, %s, %s, %s)",
                (session_id, user_id, title, now, messages_str),
            )
        conn.commit()
    finally:
        conn.close()


def delete_chat(session_id: str, user_id: str):
    """Deletes a chat session."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "DELETE FROM copilot_chats WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            )
        else:
            cursor.execute(
                "DELETE FROM copilot_chats WHERE session_id = %s AND user_id = %s",
                (session_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


# --- SQL-BASED AUTHENTICATION HELPERS ---

def save_user(
    user_id: str,
    email: str,
    name: str,
    picture: str | None,
    password_hash: str | None,
    auth_provider: str,
    username: str | None = None,
    role: str = "user",
):
    """Creates a new user record in the SQL database."""
    from app.user_scope import ROLE_USER

    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        uname = (username or email.split("@")[0]).strip().lower()
        user_role = (role or ROLE_USER).strip().lower()
        if db_type == "sqlite":
            cursor.execute(
                "INSERT INTO users (user_id, username, email, name, picture, password_hash, auth_provider, role, created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, uname, email, name, picture, password_hash, auth_provider, user_role, now.isoformat(), now.isoformat())
            )
        else:
            cursor.execute(
                "INSERT INTO users (user_id, username, email, name, picture, password_hash, auth_provider, role, created_at, last_login_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, uname, email, name, picture, password_hash, auth_provider, user_role, now, now)
            )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    """Finds a user by their email address."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        else:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict | None:
    """Finds a user by their user ID."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def update_user_login(user_id: str, name: str | None = None, picture: str | None = None):
    """Updates the user's last login time and optionally updates name/picture."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        if db_type == "sqlite":
            if name or picture:
                cursor.execute(
                    "UPDATE users SET name = COALESCE(?, name), picture = COALESCE(?, picture), last_login_at = ? WHERE user_id = ?",
                    (name, picture, now.isoformat(), user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET last_login_at = ? WHERE user_id = ?",
                    (now.isoformat(), user_id)
                )
        else:
            if name or picture:
                cursor.execute(
                    "UPDATE users SET name = COALESCE(%s, name), picture = COALESCE(%s, picture), last_login_at = %s WHERE user_id = %s",
                    (name, picture, now, user_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET last_login_at = %s WHERE user_id = %s",
                    (now, user_id)
                )
        conn.commit()
    finally:
        conn.close()


def create_session(user_id: str, session_token: str, expires_at: datetime):
    """Persists a new user session."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        if db_type == "sqlite":
            cursor.execute(
                "INSERT INTO user_sessions (session_token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (session_token, user_id, expires_at.isoformat(), now.isoformat())
            )
        else:
            cursor.execute(
                "INSERT INTO user_sessions (session_token, user_id, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                (session_token, user_id, expires_at, now)
            )
        conn.commit()
    finally:
        conn.close()


def get_session(session_token: str) -> dict | None:
    """Finds a session by token."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("SELECT * FROM user_sessions WHERE session_token = ?", (session_token,))
        else:
            cursor.execute("SELECT * FROM user_sessions WHERE session_token = %s", (session_token,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def delete_session(session_token: str):
    """Deletes a session from the database."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM user_sessions WHERE session_token = ?", (session_token,))
        else:
            cursor.execute("DELETE FROM user_sessions WHERE session_token = %s", (session_token,))
        conn.commit()
    finally:
        conn.close()


# --- AUTOMATIONS SCHEDULER HELPERS ---

def list_automations(user_id: str | None = None) -> list[dict]:
    """Retrieves automations, optionally scoped to one user (scheduler passes None for all)."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            if db_type == "sqlite":
                cursor.execute("SELECT * FROM automations WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            else:
                cursor.execute("SELECT * FROM automations WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        elif db_type == "sqlite":
            cursor.execute("SELECT * FROM automations ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM automations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        out = []
        for r in rows:
            row_dict = dict(r)
            created_at = row_dict.get("created_at")
            updated_at = row_dict.get("updated_at")
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            if isinstance(updated_at, datetime):
                updated_at = updated_at.isoformat()
            out.append({
                "id": row_dict.get("id"),
                "user_id": row_dict.get("user_id"),
                "name": row_dict.get("name"),
                "workflow_filename": row_dict.get("workflow_filename"),
                "schedule_type": row_dict.get("schedule_type"),
                "cron_expression": row_dict.get("cron_expression"),
                "interval_mins": row_dict.get("interval_mins"),
                "duration_mins": row_dict.get("duration_mins"),
                "active": bool(row_dict.get("active")),
                "author": row_dict.get("author") or "System",
                "output_filename_pattern": row_dict.get("output_filename_pattern"),
                "created_at": str(created_at) if created_at else None,
                "updated_at": str(updated_at) if updated_at else None,
            })
        return out
    finally:
        conn.close()


def get_automation(automation_id: str, user_id: str | None = None) -> dict | None:
    """Retrieves a single automation by ID."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            if db_type == "sqlite":
                cursor.execute("SELECT * FROM automations WHERE id = ? AND user_id = ?", (automation_id, user_id))
            else:
                cursor.execute("SELECT * FROM automations WHERE id = %s AND user_id = %s", (automation_id, user_id))
        elif db_type == "sqlite":
            cursor.execute("SELECT * FROM automations WHERE id = ?", (automation_id,))
        else:
            cursor.execute("SELECT * FROM automations WHERE id = %s", (automation_id,))
        row = cursor.fetchone()
        if not row:
            return None

        row_dict = dict(row)
        created_at = row_dict.get("created_at")
        updated_at = row_dict.get("updated_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
            
        return {
            "id": row_dict.get("id"),
            "user_id": row_dict.get("user_id"),
            "name": row_dict.get("name"),
            "workflow_filename": row_dict.get("workflow_filename"),
            "schedule_type": row_dict.get("schedule_type"),
            "cron_expression": row_dict.get("cron_expression"),
            "interval_mins": row_dict.get("interval_mins"),
            "duration_mins": row_dict.get("duration_mins"),
            "active": bool(row_dict.get("active")),
            "author": row_dict.get("author") or "System",
            "output_filename_pattern": row_dict.get("output_filename_pattern"),
            "created_at": str(created_at) if created_at else None,
            "updated_at": str(updated_at) if updated_at else None,
        }
    finally:
        conn.close()


def save_automation(
    automation_id: str,
    name: str,
    workflow_filename: str,
    schedule_type: str,
    cron_expression: str | None,
    interval_mins: int | None,
    duration_mins: int | None,
    active: bool,
    author: str,
    user_id: str,
    output_filename_pattern: str | None = None,
):
    """Saves or updates an automation."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.utcnow()
        active_int = 1 if active else 0

        # Try to retrieve existing to set created_at
        existing = get_automation(automation_id)
        created_at = datetime.fromisoformat(existing["created_at"]) if existing else now
        if db_type == "sqlite" and isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        if db_type == "sqlite":
            cursor.execute(
                """
                REPLACE INTO automations
                (id, user_id, name, workflow_filename, schedule_type, cron_expression, interval_mins, duration_mins, active, author, output_filename_pattern, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (automation_id, user_id, name, workflow_filename, schedule_type, cron_expression, interval_mins, duration_mins, active_int, author, output_filename_pattern, created_at, now.isoformat()),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO automations
                (id, user_id, name, workflow_filename, schedule_type, cron_expression, interval_mins, duration_mins, active, author, output_filename_pattern, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (automation_id, user_id, name, workflow_filename, schedule_type, cron_expression, interval_mins, duration_mins, active_int, author, output_filename_pattern, created_at, now),
            )
        conn.commit()
    finally:
        conn.close()


def delete_automation(automation_id: str, user_id: str | None = None):
    """Deletes an automation and all its run logs."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            if db_type == "sqlite":
                cursor.execute("DELETE FROM automation_runs WHERE automation_id = ?", (automation_id,))
                cursor.execute("DELETE FROM automations WHERE id = ? AND user_id = ?", (automation_id, user_id))
            else:
                cursor.execute("DELETE FROM automation_runs WHERE automation_id = %s", (automation_id,))
                cursor.execute("DELETE FROM automations WHERE id = %s AND user_id = %s", (automation_id, user_id))
        elif db_type == "sqlite":
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = ?", (automation_id,))
            cursor.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        else:
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = %s", (automation_id,))
            cursor.execute("DELETE FROM automations WHERE id = %s", (automation_id,))
        conn.commit()
    finally:
        conn.close()


def append_automation_run(
    run_id: str,
    automation_id: str,
    status: str,
    triggered_at: datetime,
    duration_ms: int,
    error: str | None,
    download_url: str | None = None,
):
    """Appends an execution run log for an automation."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        t_at = triggered_at.isoformat() if db_type == "sqlite" else triggered_at

        if db_type == "sqlite":
            cursor.execute(
                "INSERT INTO automation_runs (id, automation_id, run_id, status, triggered_at, duration_ms, error, download_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, automation_id, run_id, status, t_at, duration_ms, error, download_url),
            )
        else:
            cursor.execute(
                "INSERT INTO automation_runs (id, automation_id, run_id, status, triggered_at, duration_ms, error, download_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (run_id, automation_id, run_id, status, t_at, duration_ms, error, download_url),
            )
        conn.commit()
    finally:
        conn.close()


def list_automation_runs(automation_id: str, limit: int = 100) -> list[dict]:
    """Retrieves all execution logs for a specific automation."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                "SELECT * FROM automation_runs WHERE automation_id = ? ORDER BY triggered_at DESC LIMIT ?",
                (automation_id, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM automation_runs WHERE automation_id = %s ORDER BY triggered_at DESC LIMIT %s",
                (automation_id, limit),
            )
        rows = cursor.fetchall()
        
        out = []
        for r in rows:
            row_dict = dict(r)
            triggered_at = row_dict.get("triggered_at")
            if isinstance(triggered_at, datetime):
                triggered_at = triggered_at.isoformat()
            out.append({
                "id": row_dict.get("id"),
                "automation_id": row_dict.get("automation_id"),
                "run_id": row_dict.get("run_id"),
                "status": row_dict.get("status"),
                "triggered_at": str(triggered_at) if triggered_at else None,
                "duration_ms": row_dict.get("duration_ms"),
                "error": row_dict.get("error"),
                "download_url": row_dict.get("download_url"),
            })
        return out
    finally:
        conn.close()


def delete_automation_run(automation_id: str, run_id: str):
    """Deletes a single execution run log for an automation."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = ? AND run_id = ?", (automation_id, run_id))
        else:
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = %s AND run_id = %s", (automation_id, run_id))
        conn.commit()
    finally:
        conn.close()


def clear_automation_runs(automation_id: str):
    """Clears all execution run logs for a specific automation."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = ?", (automation_id,))
        else:
            cursor.execute("DELETE FROM automation_runs WHERE automation_id = %s", (automation_id,))
        conn.commit()
    finally:
        conn.close()


# --- GENERAL WORKFLOW RUN LOG HELPERS ---

def save_run_log(entry: dict):
    """Saves a run log entry to the run_logs table."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()

        def _to_json_text(value):
            if value is None:
                return None
            if isinstance(value, str):
                return value
            try:
                return json.dumps(value)
            except Exception:
                return json.dumps(str(value))

        started_at = entry.get("started_at")
        if not started_at:
            started_at = datetime.utcnow().isoformat()

        run_id = entry.get("run_id")
        user_id = entry.get("user_id")
        if not user_id:
            try:
                from app.request_context import get_current_user_id

                user_id = get_current_user_id()
            except Exception:
                user_id = None
        workflow = entry.get("workflow")
        finished_at = entry.get("finished_at")
        duration_ms = entry.get("duration_ms")
        status = entry.get("status", "success")
        disposition = entry.get("disposition")
        node_count = entry.get("node_count")
        edge_count = entry.get("edge_count")
        flag_count = entry.get("flag_count")
        error = entry.get("error")
        report_path = entry.get("report_path")
        download_url = entry.get("download_url")
        run_log = _to_json_text(entry.get("run_log"))
        run_result = _to_json_text(entry.get("run_result"))
        run_error = entry.get("run_error")

        if db_type == "sqlite":
            cursor.execute(
                """
                REPLACE INTO run_logs
                (run_id, user_id, workflow, started_at, finished_at, duration_ms, status, disposition, node_count, edge_count, flag_count, error, report_path, download_url, run_log, run_result, run_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, user_id, workflow, started_at, finished_at, duration_ms, status, disposition, node_count, edge_count, flag_count, error, report_path, download_url, run_log, run_result, run_error),
            )
        else:
            cursor.execute(
                """
                REPLACE INTO run_logs
                (run_id, user_id, workflow, started_at, finished_at, duration_ms, status, disposition, node_count, edge_count, flag_count, error, report_path, download_url, run_log, run_result, run_error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (run_id, user_id, workflow, started_at, finished_at, duration_ms, status, disposition, node_count, edge_count, flag_count, error, report_path, download_url, run_log, run_result, run_error),
            )

        artifacts = _extract_artifacts_from_run_entry(entry)
        for art in artifacts:
            source_node_id = art.get("source_node_id")
            file_name = art.get("file_name")
            artifact_type = art.get("artifact_type") or _artifact_type_from_name_or_url(file_name, art.get("download_url"))
            file_path = art.get("file_path")
            artifact_download_url = art.get("download_url")
            if not file_name and file_path:
                file_name = Path(str(file_path)).name
            if not file_name and artifact_download_url:
                file_name = Path(str(artifact_download_url)).name
            generated_at = art.get("generated_at") or datetime.utcnow().isoformat()

            if not file_name and not artifact_download_url:
                continue

            if db_type == "sqlite":
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO run_artifacts
                    (id, run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at)
                    VALUES (
                        COALESCE((
                            SELECT id FROM run_artifacts
                            WHERE run_id = ?
                              AND COALESCE(source_node_id,'') = COALESCE(?, '')
                              AND COALESCE(file_name,'') = COALESCE(?, '')
                              AND COALESCE(download_url,'') = COALESCE(?, '')
                            LIMIT 1
                        ), NULL),
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        run_id,
                        source_node_id,
                        file_name,
                        artifact_download_url,
                        run_id,
                        source_node_id,
                        file_name,
                        artifact_type,
                        file_path,
                        artifact_download_url,
                        generated_at,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO run_artifacts
                    (run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      artifact_type = VALUES(artifact_type),
                      file_path = VALUES(file_path),
                      generated_at = VALUES(generated_at)
                    """,
                    (run_id, source_node_id, file_name, artifact_type, file_path, artifact_download_url, generated_at),
                )
        conn.commit()
    finally:
        conn.close()


def _artifact_type_from_name_or_url(file_name: str | None, download_url: str | None) -> str:
    name = (file_name or "").lower()
    url = (download_url or "").lower()
    text = name or url
    if text.endswith(".xlsx") or text.endswith(".xls"):
        return "excel"
    if text.endswith(".csv"):
        return "csv"
    return "file"


def _extract_artifacts_from_run_entry(entry: dict) -> list[dict]:
    run_id = str(entry.get("run_id") or "")
    if not run_id:
        return []
    out: list[dict] = []
    now_iso = datetime.utcnow().isoformat()

    def _push(raw: dict, node_id: str | None = None) -> None:
        if not isinstance(raw, dict):
            return
        file_name = raw.get("file_name") or raw.get("filename")
        download_url = raw.get("download_url")
        file_path = raw.get("file_path") or raw.get("report_path")
        if not file_name and file_path:
            file_name = Path(str(file_path)).name
        if not file_name and download_url:
            file_name = Path(str(download_url)).name
        artifact_type = raw.get("artifact_type") or _artifact_type_from_name_or_url(file_name, download_url)
        if not file_name and not download_url:
            return
        out.append(
            {
                "run_id": run_id,
                "source_node_id": node_id or raw.get("source_node_id"),
                "file_name": file_name,
                "artifact_type": artifact_type,
                "file_path": file_path,
                "download_url": download_url,
                "generated_at": raw.get("generated_at") or now_iso,
            }
        )

    if entry.get("download_url"):
        _push(
            {
                "filename": Path(str(entry.get("download_url"))).name,
                "download_url": entry.get("download_url"),
                "report_path": entry.get("report_path"),
            }
        )

    run_result = entry.get("run_result")
    if isinstance(run_result, dict):
        _push(run_result)

    for art in entry.get("artifacts") or []:
        if isinstance(art, dict):
            _push(art, node_id=art.get("source_node_id"))

    for ev in entry.get("run_log") or []:
        if not isinstance(ev, dict):
            continue
        node_id = ev.get("node_id")
        output = ev.get("output")
        if isinstance(output, dict):
            _push(output, node_id=node_id)
            node_output = output.get("node_output")
            if isinstance(node_output, dict):
                _push(node_output, node_id=node_id)

    dedup: dict[tuple[str, str, str, str], dict] = {}
    for art in out:
        key = (
            str(art.get("run_id") or ""),
            str(art.get("file_name") or ""),
            str(art.get("download_url") or ""),
            str(art.get("artifact_type") or ""),
        )
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = art
            continue
        if not prev.get("source_node_id") and art.get("source_node_id"):
            dedup[key] = art
    return list(dedup.values())


def upsert_run_artifacts(run_id: str, artifacts: list[dict]) -> None:
    """Persist generated artifacts (csv/excel/files) for a run."""
    if not run_id or not artifacts:
        return
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        for raw in artifacts:
            if not isinstance(raw, dict):
                continue
            source_node_id = raw.get("source_node_id")
            file_name = raw.get("file_name") or raw.get("filename")
            file_path = raw.get("file_path") or raw.get("report_path")
            download_url = raw.get("download_url")
            if not file_name and file_path:
                file_name = Path(str(file_path)).name
            if not file_name and download_url:
                file_name = Path(str(download_url)).name
            generated_at = raw.get("generated_at") or now_iso
            artifact_type = raw.get("artifact_type") or _artifact_type_from_name_or_url(file_name, download_url)

            if not file_name and not download_url:
                continue

            if db_type == "sqlite":
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO run_artifacts
                    (id, run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at)
                    VALUES (
                        COALESCE((
                            SELECT id FROM run_artifacts
                            WHERE run_id = ?
                              AND COALESCE(source_node_id,'') = COALESCE(?, '')
                              AND COALESCE(file_name,'') = COALESCE(?, '')
                              AND COALESCE(download_url,'') = COALESCE(?, '')
                            LIMIT 1
                        ), NULL),
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        run_id,
                        source_node_id,
                        file_name,
                        download_url,
                        run_id,
                        source_node_id,
                        file_name,
                        artifact_type,
                        file_path,
                        download_url,
                        generated_at,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO run_artifacts
                    (run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      artifact_type = VALUES(artifact_type),
                      file_path = VALUES(file_path),
                      generated_at = VALUES(generated_at)
                    """,
                    (run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at),
                )
        conn.commit()
    finally:
        conn.close()


def list_run_artifacts(run_id: str) -> list[dict]:
    """Get all artifacts for a run (newest first)."""
    if not run_id:
        return []
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if db_type == "sqlite":
            cursor.execute(
                """
                SELECT run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at
                FROM run_artifacts
                WHERE run_id = ?
                ORDER BY generated_at DESC
                """,
                (run_id,),
            )
        else:
            cursor.execute(
                """
                SELECT run_id, source_node_id, file_name, artifact_type, file_path, download_url, generated_at
                FROM run_artifacts
                WHERE run_id = %s
                ORDER BY generated_at DESC
                """,
                (run_id,),
            )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clear_run_artifacts(run_id: str | None = None) -> None:
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if run_id:
            if db_type == "sqlite":
                cursor.execute("DELETE FROM run_artifacts WHERE run_id = ?", (run_id,))
            else:
                cursor.execute("DELETE FROM run_artifacts WHERE run_id = %s", (run_id,))
        else:
            cursor.execute("DELETE FROM run_artifacts")
        conn.commit()
    finally:
        conn.close()


def list_db_run_logs(
    limit: int = 200,
    *,
    user_id: str | None = None,
    workflow: str | None = None,
    status: str | None = None,
    disposition: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Retrieves run logs, sorted by started_at descending, with optional filters."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        clauses: list[str] = []
        params: list[Any] = []

        if user_id:
            clauses.append("user_id = ?" if db_type == "sqlite" else "user_id = %s")
            params.append(user_id)
        if workflow:
            if db_type == "sqlite":
                clauses.append("workflow LIKE ? COLLATE NOCASE")
            else:
                clauses.append("LOWER(workflow) LIKE LOWER(%s)")
            params.append(f"%{workflow}%")
        if status:
            clauses.append("status = ?" if db_type == "sqlite" else "status = %s")
            params.append(status)
        if disposition:
            clauses.append("disposition = ?" if db_type == "sqlite" else "disposition = %s")
            params.append(disposition)
        if since:
            clauses.append("started_at >= ?" if db_type == "sqlite" else "started_at >= %s")
            params.append(since)
        if until:
            clauses.append("started_at <= ?" if db_type == "sqlite" else "started_at <= %s")
            params.append(until)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order_limit = " ORDER BY started_at DESC LIMIT ?" if db_type == "sqlite" else " ORDER BY started_at DESC LIMIT %s"
        params.append(limit)
        cursor.execute(f"SELECT * FROM run_logs{where}{order_limit}", tuple(params))
        rows = cursor.fetchall()
        out: list[dict] = []
        for row in rows:
            item = _normalize_run_log_row(dict(row))
            out.append(item)
        return out
    finally:
        conn.close()


def _normalize_run_log_row(item: dict) -> dict:
    for field in ("run_log", "run_result"):
        raw = item.get(field)
        if raw in (None, ""):
            item[field] = None
            continue
        if isinstance(raw, (dict, list)):
            continue
        try:
            item[field] = json.loads(raw)
        except Exception:
            item[field] = None

    if not item.get("run_error") and item.get("error"):
        item["run_error"] = item.get("error")

    run_id = item.get("run_id")
    item["artifacts"] = list_run_artifacts(str(run_id)) if run_id else []
    return item


def get_run_log_db(run_id: str, user_id: str | None = None) -> dict | None:
    """Fetch a single run log row by run_id, optionally scoped to a user."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            if db_type == "sqlite":
                cursor.execute("SELECT * FROM run_logs WHERE run_id = ? AND user_id = ?", (run_id, user_id))
            else:
                cursor.execute("SELECT * FROM run_logs WHERE run_id = %s AND user_id = %s", (run_id, user_id))
        elif db_type == "sqlite":
            cursor.execute("SELECT * FROM run_logs WHERE run_id = ?", (run_id,))
        else:
            cursor.execute("SELECT * FROM run_logs WHERE run_id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return _normalize_run_log_row(dict(row))
    finally:
        conn.close()


def _workflow_row_updated_ms(updated_at: str | datetime | None) -> int:
    if not updated_at:
        return 0
    try:
        if isinstance(updated_at, datetime):
            return int(updated_at.timestamp() * 1000)
        iso_str = str(updated_at).replace("Z", "+00:00")
        return int(datetime.fromisoformat(iso_str).timestamp() * 1000)
    except Exception:
        return 0


def list_workflow_library_rows(user_id: str) -> list[dict]:
    """Saved workflows and drafts for one user — same source as the Templates drawer."""
    rows: list[dict] = []
    for row in list_workflows_db(user_id):
        tagged = dict(row)
        tagged["_library_kind"] = "saved"
        rows.append(tagged)
    for row in list_drafts_db(user_id):
        tagged = dict(row)
        tagged["_library_kind"] = "draft"
        rows.append(tagged)
    return rows


def _workflow_row_to_dag(row: dict) -> dict | None:
    raw = row.get("workflow_data")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def get_workflow_by_name_db(name: str, user_id: str) -> dict | None:
    """Find workflow JSON by display name via the canonical workflow catalog."""
    from app.workflow_library import get_workflow_by_canonical_name

    return get_workflow_by_canonical_name(name, user_id)


def workflow_exists_in_library(name: str, user_id: str) -> bool:
    """True when a saved or draft workflow matches via the canonical catalog."""
    from app.workflow_library import workflow_exists_in_catalog

    return workflow_exists_in_catalog(name, user_id)


def list_recent_run_workflow_names(limit: int = 5, user_id: str | None = None) -> list[str]:
    """Distinct workflow names from recent runs (newest first)."""
    logs = list_db_run_logs(limit=limit * 3, user_id=user_id)
    seen: set[str] = set()
    names: list[str] = []
    for row in logs:
        wf = str(row.get("workflow") or "").strip()
        if wf and wf not in seen:
            seen.add(wf)
            names.append(wf)
        if len(names) >= limit:
            break
    return names


def clear_db_run_logs(user_id: str | None = None):
    """Deletes run log entries, optionally scoped to one user."""
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        if user_id:
            if db_type == "sqlite":
                cursor.execute(
                    "DELETE FROM run_artifacts WHERE run_id IN (SELECT run_id FROM run_logs WHERE user_id = ?)",
                    (user_id,),
                )
                cursor.execute("DELETE FROM run_logs WHERE user_id = ?", (user_id,))
            else:
                cursor.execute(
                    "DELETE FROM run_artifacts WHERE run_id IN (SELECT run_id FROM run_logs WHERE user_id = %s)",
                    (user_id,),
                )
                cursor.execute("DELETE FROM run_logs WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM run_logs")
            cursor.execute("DELETE FROM run_artifacts")
        conn.commit()
    finally:
        conn.close()


def clear_all_workspace_data(user_id: str) -> dict[str, int]:
    """Delete one user's workload data. Preserves auth accounts and global good_examples."""
    conn, db_type = get_connection()
    deleted: dict[str, int] = {}
    try:
        cursor = conn.cursor()
        scoped_tables = (
            ("automation_runs", "automation_id IN (SELECT id FROM automations WHERE user_id = ?)"),
            ("automations", "user_id = ?"),
            ("run_artifacts", "run_id IN (SELECT run_id FROM run_logs WHERE user_id = ?)"),
            ("run_logs", "user_id = ?"),
            ("drafts", "user_id = ?"),
            ("workflows", "user_id = ?"),
            ("copilot_chats", "user_id = ?"),
            ("user_memory", "user_id = ?"),
            ("user_skills", "user_id = ?"),
            ("workflow_votes", "voter_user_id = ? OR owner_user_id = ?"),
        )
        for table, where in scoped_tables:
            if table == "workflow_votes":
                if db_type == "sqlite":
                    cursor.execute(f"DELETE FROM {table} WHERE {where}", (user_id, user_id))
                else:
                    cursor.execute(
                        f"DELETE FROM {table} WHERE voter_user_id = %s OR owner_user_id = %s",
                        (user_id, user_id),
                    )
            elif db_type == "sqlite":
                cursor.execute(f"DELETE FROM {table} WHERE {where}", (user_id,))
            else:
                cursor.execute(f"DELETE FROM {table} WHERE {where.replace('?', '%s')}", (user_id,))
            deleted[table] = cursor.rowcount if cursor.rowcount is not None else 0
        conn.commit()
    finally:
        conn.close()
    return deleted

