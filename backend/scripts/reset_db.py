import os
import sys
from pathlib import Path

# Add backend directory to python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.database import get_connection, init_db

TABLES = [
    "workflow_votes",
    "good_examples",
    "automation_runs",
    "automations",
    "run_artifacts",
    "run_logs",
    "drafts",
    "workflows",
    "copilot_chats",
    "user_memory",
    "user_preferences",
    "user_skills",
    "user_data_source_access",
    "user_feature_access",
    "user_sessions",
    "users",
]


def reset_database():
    print("Connecting to database...")
    conn, db_type = get_connection()
    try:
        cursor = conn.cursor()
        print(f"Detected database type: {db_type}")
        print("Dropping tables if they exist...")

        if db_type == "sqlite":
            cursor.execute("PRAGMA foreign_keys = OFF;")
        else:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        for table in TABLES:
            print(f"Dropping table {table}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table};")

        if db_type == "sqlite":
            cursor.execute("PRAGMA foreign_keys = ON;")
        else:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        conn.commit()
        print("All tables successfully dropped.")
    finally:
        conn.close()

    print("Re-initializing database schema and seeding default user + workflows...")
    init_db()
    print("Database has been reset completely afresh!")


if __name__ == "__main__":
    reset_database()
