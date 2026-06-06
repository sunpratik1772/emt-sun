# dbSherpa — Database scripts & schema (v5)

Canonical SQL for **16 tables**, schema version **5** (`database_scope.SCHEMA_VERSION`).

| Engine | Script | Apply |
|--------|--------|-------|
| **MySQL 8 / Cloud SQL** | [`backend/sql/001_schema_mysql.sql`](../../backend/sql/001_schema_mysql.sql) | `python3 backend/scripts/apply_mysql_schema.py` |
| **SQLite (local dev)** | [`backend/sql/002_schema_sqlite.sql`](../../backend/sql/002_schema_sqlite.sql) | `python3 backend/scripts/apply_sqlite_schema.py` |
| **Legacy reference** | [`backend/sql/schema.sql`](../../backend/sql/schema.sql) | Same as SQLite; prefer `002_schema_sqlite.sql` |

After applying schema, start the API once — `init_db()` runs migrations and seeds the demo admin (`johndoe` / `password123`).

---

## Verify

```bash
python3 backend/scripts/verify_schema.py
```

Checks all 16 tables and required columns against the live connection (SQLite or MySQL).

---

## Docs in this folder

| Doc | Contents |
|-----|----------|
| **[relations.md](./relations.md)** | ER diagram, every table, logical FKs, access-control model |
| **[cloud-sql.md](./cloud-sql.md)** | Google Cloud SQL setup, Auth Proxy, Cloud Run env vars |

High-level ops guide: **[../database.md](../database.md)**.

---

## Quick reference — 16 tables

**Auth & identity:** `users`, `user_sessions`

**Per-user workspace:** `workflows`, `drafts`, `workflow_votes`, `good_examples`

**Copilot:** `copilot_chats`, `user_memory`

**Access control:** `user_skills`, `user_data_source_access`, `user_preferences`, `user_feature_access`

**Runs:** `run_logs`, `run_artifacts`

**Automations:** `automations`, `automation_runs`

---

## Connection env vars

```env
# MySQL / Cloud SQL (TCP)
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=dbsherpa
MYSQL_PASSWORD=...
MYSQL_DATABASE=dbsherpa

# Or unified URL
DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbsherpa

# Cloud SQL via Unix socket (Cloud Run + Auth Proxy sidecar)
MYSQL_UNIX_SOCKET=/cloudsql/PROJECT:REGION:INSTANCE
# alias:
CLOUD_SQL_UNIX_SOCKET=/cloudsql/PROJECT:REGION:INSTANCE
```

Unset `MYSQL_*` and `DATABASE_URL` → SQLite file at `backend/copilot_chats.db`.

---

## Dev reset (destructive)

```bash
python3 backend/scripts/reset_db.py
```

Drops all tables, re-applies schema via `init_db()`, re-seeds workflows from disk.
