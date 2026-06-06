# Data Source Onboarding

> Register datasets so Copilot, `db_query`, and `csv_extract` nodes know column names and demo rows.
>
> **All datasets use the Oracle SQL connector** (`connector: oracle`).

**Package:** `backend/connectors/`  
**Catalog YAML:** `backend/connectors/metadata/<id>.yaml`  
**Registry:** `connectors.catalog.DataSourceRegistry` + `connectors.registry.ConnectorRegistry`

---

## Overview

Each dataset is one YAML file under `connectors/metadata/`. At startup the registry loads all YAMLs and routes them through `OracleConnector`.

```
connectors/metadata/orders.csv.yaml  →  oracle:DEMO.ORDERS (demo table `orders`)
connectors/metadata/hs_alerts.yaml   →  oracle:SURVEILLANCE.HS_ALERTS
```

Copilot reads schemas via `GET /api/data-sources` and embeds them in generation prompts through `generation/harness/enrichment.py`.

---

## Directory layout

```
backend/connectors/
├── catalog.py              DataSource, DataSourceRegistry
├── registry.py             ConnectorRegistry, get_rows()
├── oracle_connector.py     Oracle SQL (demo fixture + live DSN)
├── sql_fixture.py          Demo DB helpers (when ORACLE_DSN unset)
└── metadata/
    ├── orders.csv.yaml
    ├── hs_alerts.yaml
    └── …
```

---

## Step 1: Add metadata YAML

```yaml
id: my_table
description: Short description for Copilot
connector: oracle
sources:
  - oracle:MYSCHEMA.MY_TABLE
columns:
  - { name: id, type: string }
  - { name: amount, type: number, semantic: notional }
```

Print a copy-paste template:

```bash
cd backend
python3 -c "from connectors.oracle_connector import OracleConnector; print(OracleConnector.onboarding_template().yaml_template)"
```

---

## Step 2: Demo fixture (local dev)

When `ORACLE_DSN` is unset, `OracleConnector` reads from `demo_data/surveillance_fixture.sqlite`.

1. Add table DDL + seed data in `scripts/gen_sqlite_demo_data.py`.
2. Map `oracle:MYSCHEMA.MY_TABLE` → table name in `oracle_connector._DEMO_TABLE_MAP`.
3. Regenerate: `python3 scripts/gen_sqlite_demo_data.py`

---

## Step 3: Workflows

Use **`db_query`** with SQL against the demo table name:

```json
{ "source": "comms_messages", "query": "SELECT * FROM comms_messages LIMIT 20" }
```

`csv_extract` still works as a convenience loader (`get_rows` via Oracle).

---

## Production

Set `ORACLE_DSN` and implement `OracleConnector._query_oracle` with `oracledb` or SQLAlchemy.
