"""DB query — runs SELECT against Oracle-backed datasets (demo fixture when ORACLE_DSN unset)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from connectors.base import ConnectorKind
from connectors.catalog import get_registry
from connectors.oracle_connector import execute_demo_query
from connectors.registry import dataset_names, get_rows
from ..context import RunContext
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent

_SELECT_RE = re.compile(r"^\s*select\b", re.I)
_LIMIT_RE = re.compile(r"\blimit\s+(\d+)\b", re.I)
_FROM_RE = re.compile(r"\bfrom\s+([\w.]+)", re.I)


def _parse_limit(query: str) -> int | None:
    m = _LIMIT_RE.search(query)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except ValueError:
        return None
    return n if n > 0 else None


def _infer_source(query: str) -> str | None:
    m = _FROM_RE.search(query)
    if not m:
        return None
    tbl = m.group(1)
    for ds in dataset_names():
        if ds.split(".")[0] == tbl or ds == tbl:
            return ds
    return None


def _oracle_backed(source: str) -> bool:
    entry = get_registry().get(source)
    return entry is not None and entry.connector == ConnectorKind.ORACLE


def _apply_row_limit(rows: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None:
        return rows
    return rows[:limit]


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    query = (cfg.get("query") or "").strip()
    source = cfg.get("source") or _infer_source(query)

    limit = cfg.get("limit")
    parsed_limit: int | None = None
    if isinstance(limit, (int, float)) and int(limit) > 0:
        parsed_limit = int(limit)
    elif query:
        parsed_limit = _parse_limit(query)

    rows: list[dict[str, Any]] = []
    if query and _oracle_backed(source or ""):
        executed = execute_demo_query(query)
        if executed is not None:
            rows = executed
    if not rows and source:
        rows = get_rows(source)
    if rows and parsed_limit is not None:
        rows = _apply_row_limit(rows, parsed_limit)

    return {"query": query, "source": source, "rows": rows, "rowCount": len(rows)}


NODE_SPEC = _spec_from_yaml(_HERE / "db_query.yaml", run)
