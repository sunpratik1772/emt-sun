# Connectors

All datasets use the **Oracle** SQL connector (`connector: oracle`).

## Onboarding

1. Copy `OracleConnector.onboarding_template()` from `oracle_connector.py`.
2. Add `metadata/<table_id>.yaml` with `sources: [oracle:SCHEMA.TABLE]` and columns.
3. For local demo, register the table in `scripts/gen_sqlite_demo_data.py` (fixture DB).

## Demo vs production

| Mode | Behavior |
|------|----------|
| Demo (default) | `ORACLE_DSN` unset → reads from `demo_data/surveillance_fixture.sqlite` via `sql_fixture.py` |
| Production | Set `ORACLE_DSN` and implement `OracleConnector._query_oracle` |

## Layout

```
connectors/
├── catalog.py           YAML → DataSourceRegistry
├── registry.py          get_rows() → OracleConnector
├── oracle_connector.py  Oracle SQL (demo + live)
├── sql_fixture.py       Demo fixture helpers
└── metadata/*.yaml      One file per dataset
```
