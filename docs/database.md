# dbSherpa Studio — Database schema & operations

> Persistence for auth, multi-user scoping, Copilot chat, workflow library, run logs,
> and scheduled automations. **Default: SQLite** (zero config). **Production: MySQL 8**
> (Google Cloud SQL).

**Implementation:** `backend/app/database.py`  
**Migrations & seed:** `backend/app/database_scope.py` (schema v5)  
**SQL scripts & ER diagram:** **[docs/db/](./db/README.md)**  
**Cloud SQL guide:** **[docs/db/cloud-sql.md](./db/cloud-sql.md)**

---

## Architecture

```
FastAPI (server.py)
    │
    ├── lifespan → init_db() on startup
    │
    └── app.database.get_connection()
            │
            ├── SQLite (default)
            │     backend/copilot_chats.db
            │
            └── MySQL / Cloud SQL (when configured)
                  DATABASE_URL or MYSQL_* env vars
                  optional MYSQL_UNIX_SOCKET for Cloud Run
```

**Not the same as demo surveillance data:** workflow `db_query` nodes read from
`backend/demo_data/surveillance_fixture.sqlite` via `connectors/sqlite_demo.py`.
That is separate from the app persistence DB.

---

## Tables (16)

Full column lists and relationships: **[docs/db/relations.md](./db/relations.md)**

| Group | Tables |
|-------|--------|
| Auth | `users`, `user_sessions` |
| Workspace | `workflows`, `drafts`, `workflow_votes`, `good_examples` |
| Copilot | `copilot_chats`, `user_memory` |
| Access control | `user_skills`, `user_data_source_access`, `user_preferences`, `user_feature_access` |
| Runs | `run_logs`, `run_artifacts` |
| Automations | `automations`, `automation_runs` |

### Notable columns (v5)

- **`users.username`** — login handle (unique)
- **`users.role`** — `user` or `admin`
- **`workflows` / `drafts`** — composite PK `(user_id, filename)` per-user namespaces
- **`run_logs.user_id`** — run history scoped to owner
- **`user_feature_access`** — coarse feature toggles (`workflows`, `run_history`, `data_sources`, `skills`, `node_palette`, `automations`)

Only one SQL foreign key is declared: `automation_runs.automation_id → automations.id`.

---

## Schema scripts

| Engine | File | Apply |
|--------|------|-------|
| MySQL / Cloud SQL | `backend/sql/001_schema_mysql.sql` | `python3 backend/scripts/apply_mysql_schema.py` |
| SQLite | `backend/sql/002_schema_sqlite.sql` | `python3 backend/scripts/apply_sqlite_schema.py` |

Verify live DB matches code:

```bash
python3 backend/scripts/verify_schema.py
```

---

## Local development

### SQLite (default)

No configuration. File created at `backend/copilot_chats.db` on first request.

### Reset database (destructive)

```bash
python3 backend/scripts/reset_db.py
```

Drops all 16 tables and re-runs `init_db()` including workflow seeding.

### MySQL via Docker

```bash
docker run --name dbsherpa-mysql \
  -e MYSQL_ROOT_PASSWORD=secret \
  -e MYSQL_DATABASE=dbsherpa \
  -p 3306:3306 \
  -d mysql:8.0

python3 backend/scripts/apply_mysql_schema.py
python3 backend/scripts/verify_schema.py
```

`backend/.env`:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=secret
MYSQL_DATABASE=dbsherpa
```

Or:

```env
DATABASE_URL=mysql+pymysql://root:secret@127.0.0.1:3306/dbsherpa
```

### Seed admin (dev)

On empty `users` table, `init_db()` creates:

| | Default |
|--|---------|
| Username | `johndoe` |
| Password | `password123` |
| Role | `admin` |

Override: `DBSHERPA_SEED_USERNAME`, `DBSHERPA_SEED_PASSWORD`, etc.

---

## Scheduler integration

`backend/app/scheduler.py` runs inside the FastAPI process:

1. Every 10s, query `automations` where `active = 1`
2. For **cron**: match current minute against expression
3. For **interval**: check elapsed time since last run within `duration_mins` window
4. Load workflow JSON, call DAG runner, persist to `run_logs` + `automation_runs`

Manual trigger: `POST /api/automations/{id}/trigger`

---

## API surface

| Router | Endpoints |
|--------|-----------|
| `auth.py` | `/auth/register`, `/login`, `/logout`, `/me`, `/session` |
| `user.py` | `/user/users`, `/user/admin/overview`, per-user access CRUD |
| `copilot.py` | `/copilot/chats`, `/copilot/chats/{id}` |
| `library.py` | `/run-logs`, `/audit-logs` |
| `automations.py` | `/automations`, `/automations/{id}/runs`, `/automations/{id}/trigger` |
| `workflows.py` | Per-user workflow CRUD |

---

## Migration notes

- MongoDB removed in favor of SQL backends
- Schema v5 adds multi-user scoping, access control tables, votes, good examples
- Runtime migrations in `database_scope.py` are idempotent — safe on startup
- For greenfield Cloud SQL, apply `001_schema_mysql.sql` before first deploy
