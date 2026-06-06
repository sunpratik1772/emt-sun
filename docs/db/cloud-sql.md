# Google Cloud SQL — dbSherpa setup

Step-by-step for a **MySQL 8** instance that matches local schema v5. Designed for Cloud Run + Cloud SQL Auth Proxy.

---

## 1. Create the instance

```bash
gcloud sql instances create dbsherpa-db \
  --database-version=MYSQL_8_0 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password='CHOOSE_A_STRONG_PASSWORD'
```

Create database and app user:

```bash
gcloud sql databases create dbsherpa --instance=dbsherpa-db

gcloud sql users create dbsherpa_app \
  --instance=dbsherpa-db \
  --password='APP_USER_PASSWORD'
```

Grant the app user only what it needs (via Cloud Console → Users, or connect as root):

```sql
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP
  ON dbsherpa.* TO 'dbsherpa_app'@'%';
FLUSH PRIVILEGES;
```

---

## 2. Apply schema

### Option A — from your laptop (Auth Proxy)

```bash
# Terminal 1 — proxy
cloud-sql-proxy PROJECT_ID:us-central1:dbsherpa-db --port 3306

# Terminal 2 — apply
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=dbsherpa_app
export MYSQL_PASSWORD='APP_USER_PASSWORD'
export MYSQL_DATABASE=dbsherpa

python3 backend/scripts/apply_mysql_schema.py
python3 backend/scripts/verify_schema.py
```

### Option B — raw mysql client

```bash
mysql -h 127.0.0.1 -P 3306 -u dbsherpa_app -p dbsherpa \
  < backend/sql/001_schema_mysql.sql
```

### Option C — let the API bootstrap

Start the backend pointed at an **empty** database. `init_db()` creates any missing tables via `database_scope.py`. For production, prefer **Option A** so indexes and the `automation_runs` FK exist before traffic.

---

## 3. Cloud Run environment

### TCP via Auth Proxy sidecar (common pattern)

```yaml
# cloud-run service snippet
env:
  - name: MYSQL_HOST
    value: "127.0.0.1"
  - name: MYSQL_PORT
    value: "3306"
  - name: MYSQL_USER
    value: dbsherpa_app
  - name: MYSQL_PASSWORD
    valueFrom:
      secretKeyRef:
        name: dbsherpa-mysql-password
        key: latest
  - name: MYSQL_DATABASE
    value: dbsherpa
```

Attach Cloud SQL connection on the service (`--add-cloudsql-instances=PROJECT:REGION:INSTANCE`).

### Unix socket (direct Cloud SQL connector)

When the Cloud Run service mounts the Cloud SQL socket:

```env
MYSQL_UNIX_SOCKET=/cloudsql/PROJECT_ID:us-central1:dbsherpa-db
MYSQL_USER=dbsherpa_app
MYSQL_PASSWORD=...
MYSQL_DATABASE=dbsherpa
```

`database.py` reads `MYSQL_UNIX_SOCKET` or `CLOUD_SQL_UNIX_SOCKET` and connects without `host`/`port`.

---

## 4. Seed user & app data

On first API start with an empty `users` table:

| Field | Default |
|-------|---------|
| Username | `johndoe` |
| Password | `password123` |
| Email | `john.doe@dbsherpa.local` |
| Role | `admin` |

Override via env:

```env
DBSHERPA_SEED_USERNAME=johndoe
DBSHERPA_SEED_PASSWORD=password123
DBSHERPA_SEED_EMAIL=john.doe@dbsherpa.local
DBSHERPA_SEED_NAME=John Doe
```

**Change the seed password in production** before exposing the service.

Workflow library rows are seeded from `backend/workflows/` when the table is empty.

---

## 5. Health check

```bash
curl -s https://YOUR_SERVICE/api/health
```

With auth:

```bash
curl -s -X POST https://YOUR_SERVICE/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"johndoe","password":"password123"}'
```

---

## 6. Local ↔ Cloud parity checklist

| Step | Command / action |
|------|------------------|
| Schema files match code | `python3 backend/scripts/verify_schema.py` (local SQLite) |
| MySQL schema applied | `apply_mysql_schema.py` against Cloud SQL |
| MySQL verify | `verify_schema.py` with `MYSQL_*` set |
| Migrations idempotent | Restart API twice; no errors in logs |
| Multi-user scoping | Create user in Settings → confirm isolated workflows/runs |

---

## 7. Backup & restore

```bash
# Export
gcloud sql export sql dbsherpa-db gs://YOUR_BUCKET/dbsherpa-$(date +%Y%m%d).sql \
  --database=dbsherpa

# Import (new instance)
gcloud sql import sql dbsherpa-db gs://YOUR_BUCKET/dbsherpa-20260605.sql \
  --database=dbsherpa
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Access denied for user` | Check user host `%`, password secret, database name |
| `Table doesn't exist` | Run `apply_mysql_schema.py` or start API once |
| `verify_schema.py` missing columns | Run latest code; `init_db()` migrates additive columns |
| Connection timeout from laptop | Use Cloud SQL Auth Proxy, whitelist IP, or socket on Cloud Run |
| SQLite in prod by accident | Ensure `MYSQL_HOST` or `DATABASE_URL` is set in Cloud Run |

---

## File reference

| File | Purpose |
|------|---------|
| `backend/sql/001_schema_mysql.sql` | Full DDL for Cloud SQL |
| `backend/scripts/apply_mysql_schema.py` | Apply DDL programmatically |
| `backend/scripts/verify_schema.py` | Column/table parity check |
| `backend/app/database.py` | Connection + `init_db()` |
| `backend/app/database_scope.py` | Migrations + seed |
| `docs/db/relations.md` | All table relationships |
