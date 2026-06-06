"""
Oracle SQL connector — one table per metadata YAML.

Binding ref format: ``oracle:<SCHEMA>.<TABLE>`` (e.g. ``oracle:DEMO.ORDERS``).

Production: set ``ORACLE_DSN`` and implement ``_query_oracle``.
Demo: maps Oracle refs to tables in ``demo_data/surveillance_fixture.sqlite``.
"""
from __future__ import annotations

import os
import re
from typing import Any

from connectors.base import BaseConnector, ConnectorKind, OnboardingTemplate, TableBinding

# Oracle schema.table → demo fixture SQLite table (local dev only).
_DEMO_TABLE_MAP: dict[str, str] = {
    "DEMO.LEADS": "leads",
    "DEMO.ORDERS": "orders",
    "DEMO.PRODUCTS": "products",
    "SURVEILLANCE.HS_ALERTS": "hs_alerts",
    "SURVEILLANCE.HS_ORDERS": "hs_orders",
    "SURVEILLANCE.HS_EXEC": "hs_exec",
    "SURVEILLANCE.HS_TRADES": "hs_trades",
    "SURVEILLANCE.MARKET_TICKS": "market_ticks",
    "SURVEILLANCE.COMMS_MESSAGES": "comms_messages",
}

_ONBOARDING_YAML = """\
# Copy to connectors/metadata/<table_id>.yaml
id: ebs_trades
description: EBS trade rows from Oracle
connector: oracle
sources:
  - oracle:EBS.TRADES
columns:
  - { name: trade_id, type: string }
  - { name: trader_id, type: string, semantic: trader }
  - { name: notional, type: number, semantic: notional }
  - { name: trade_time, type: datetime, semantic: time }
"""


def resolve_demo_table(table_ref: str) -> str | None:
    """Map ``oracle:SCHEMA.TABLE`` to a demo fixture table name."""
    key = table_ref.strip().upper()
    if key in _DEMO_TABLE_MAP:
        return _DEMO_TABLE_MAP[key]
    if "." in key:
        tail = key.split(".")[-1].lower()
        if tail.isidentifier():
            return tail
    lowered = key.lower()
    return lowered if lowered.isidentifier() else None


def execute_demo_query(query: str) -> list[dict[str, Any]] | None:
    """Run a SELECT against the demo fixture when ``ORACLE_DSN`` is unset."""
    if not re.match(r"^\s*select\b", query, re.I):
        return None
    from connectors.sql_fixture import execute_select

    try:
        return execute_select(query)
    except Exception:
        return None


class OracleConnector(BaseConnector):
    kind = ConnectorKind.ORACLE

    def fetch_rows(
        self,
        binding: TableBinding,
        *,
        raw_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        table_ref = binding.ref.split(":", 1)[-1].strip()
        dsn = os.getenv("ORACLE_DSN", "").strip()
        if dsn:
            return self._query_oracle(dsn, table_ref, raw_metadata or {})
        demo_table = resolve_demo_table(table_ref)
        if not demo_table:
            return []
        from connectors.sql_fixture import fetch_table

        return fetch_table(demo_table)

    def _query_oracle(
        self,
        dsn: str,
        table_ref: str,
        raw_metadata: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Live Oracle query — implement with oracledb for your environment."""
        raise NotImplementedError(
            f"Live Oracle query not configured for {table_ref!r}. "
            "Set ORACLE_DSN and implement OracleConnector._query_oracle."
        )

    @classmethod
    def onboarding_template(cls) -> OnboardingTemplate:
        return OnboardingTemplate(
            connector_kind=ConnectorKind.ORACLE,
            yaml_template=_ONBOARDING_YAML,
            readme=(
                "Onboard one Oracle table: copy YAML to connectors/metadata/, "
                "set connector: oracle, sources: [oracle:SCHEMA.TABLE], define columns."
            ),
        )
