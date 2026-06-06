"""
Unified data connector framework — Oracle SQL only.

Each onboarded table is one YAML file under ``metadata/`` with
``connector: oracle`` and ``sources: [oracle:SCHEMA.TABLE]``.

Onboarding a new table
----------------------
1. Copy ``OracleConnector.onboarding_template()`` YAML.
2. Add ``connectors/metadata/<table_id>.yaml`` with columns + binding.
3. Register the table in ``scripts/gen_sqlite_demo_data.py`` (demo fixture) or
   implement live queries when ``ORACLE_DSN`` is set.
"""
from connectors.catalog import (
    ColumnSpec,
    DataSource,
    DataSourceRegistry,
    SourceSchema,
    get_registry,
    split_source_ref,
)
from connectors.registry import ConnectorRegistry, dataset_names, get_rows

__all__ = [
    "ColumnSpec",
    "ConnectorRegistry",
    "DataSource",
    "DataSourceRegistry",
    "SourceSchema",
    "dataset_names",
    "get_registry",
    "get_rows",
    "split_source_ref",
]
