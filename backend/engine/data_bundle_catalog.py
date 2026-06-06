"""
Registry-backed catalog for load specs, join keys, and Excel export blueprints.

Used by the harness blueprint router when a user asks for Excel output over
one or more known data bundles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from connectors import get_registry

_CSV_SUFFIX = ".csv"
_PREFERRED_JOIN_KEYS = (
    "alert_id",
    "order_id",
    "exec_id",
    "sku",
    "participant_id",
    "lead_id",
    "message_id",
    "trade_id",
)


@dataclass(frozen=True)
class BundleLoadSpec:
    bundle_id: str
    node_type: str
    config: dict[str, Any]


@dataclass(frozen=True)
class JoinPairSpec:
    left_id: str
    right_id: str
    left_key: str
    right_key: str
    join_type: str = "inner"
    demo_filename: str | None = None


# Vetted join pairs — demo_filename overrides synthesized skeleton when present.
JOIN_PAIRS: tuple[JoinPairSpec, ...] = (
    JoinPairSpec(
        "orders.csv",
        "products.csv",
        "sku",
        "sku",
        demo_filename="studio_04_product_360_join.json",
    ),
    JoinPairSpec("hs_alerts", "market_ticks", "alert_id", "alert_id"),
    JoinPairSpec("hs_alerts", "comms_messages", "alert_id", "alert_id"),
    JoinPairSpec("hs_alerts", "hs_trades", "alert_id", "alert_id"),
    JoinPairSpec("hs_alerts", "hs_orders", "alert_id", "alert_id"),
    JoinPairSpec("hs_alerts", "hs_exec", "alert_id", "alert_id"),
    JoinPairSpec("hs_orders", "hs_exec", "order_id", "order_id"),
    JoinPairSpec("hs_trades", "hs_exec", "exec_id", "exec_id"),
    JoinPairSpec("hs_trades", "hs_orders", "order_id", "order_id"),
    JoinPairSpec("comms_messages", "hs_trades", "alert_id", "alert_id"),
)

_DATASET_ALIASES: dict[str, str] = {
    "orders": "orders.csv",
    "products": "products.csv",
    "leads": "leads.csv",
}


def all_bundle_ids() -> tuple[str, ...]:
    return tuple(s.id for s in get_registry().all())


def is_csv_bundle(bundle_id: str) -> bool:
    """Legacy id suffix only — all bundles load via db_query + Oracle."""
    return False


def _sql_table(bundle_id: str) -> str:
    from connectors.oracle_connector import resolve_demo_table

    ds = get_registry().get(bundle_id)
    if ds is not None:
        for src in ds.sources:
            if isinstance(src, str) and src.startswith("oracle:"):
                ref = src.split(":", 1)[1].strip()
                table = resolve_demo_table(ref)
                if table:
                    return table
    return bundle_id.split(".")[0]


def _select_columns(bundle_id: str) -> list[str]:
    ds = get_registry().get(bundle_id)
    if ds is None:
        return []
    cols = [c.name for c in ds.columns if c.include_in_tab]
    return cols[:12] if cols else [c.name for c in ds.columns[:12]]


def build_load_spec(bundle_id: str) -> BundleLoadSpec:
    table = _sql_table(bundle_id)
    cols = _select_columns(bundle_id)
    if cols:
        query = f"SELECT {', '.join(cols)} FROM {table}"
    else:
        query = f"SELECT * FROM {table}"
    return BundleLoadSpec(bundle_id, "db_query", {"query": query, "source": bundle_id})


def infer_join_keys(left_id: str, right_id: str) -> tuple[str, str] | None:
    reg = get_registry()
    left_cols = set(reg.column_names(left_id))
    right_cols = set(reg.column_names(right_id))
    shared = left_cols & right_cols
    for key in _PREFERRED_JOIN_KEYS:
        if key in shared:
            return key, key
    if len(shared) == 1:
        only = next(iter(shared))
        return only, only
    return None


def resolve_join_pair(datasets: list[str]) -> JoinPairSpec | None:
    ds_set = set(datasets)
    for pair in JOIN_PAIRS:
        if pair.left_id in ds_set and pair.right_id in ds_set:
            return pair
    if len(datasets) >= 2:
        for i, left in enumerate(datasets):
            for right in datasets[i + 1 :]:
                keys = infer_join_keys(left, right)
                if keys:
                    return JoinPairSpec(left, right, keys[0], keys[1])
    return None


def datasets_in_scenario(scenario: str) -> tuple[str, ...]:
    """Match registry bundle ids (and common aliases) mentioned in free text."""
    lower = scenario.lower()
    tokens = set(re.findall(r"[a-z][a-z0-9_.-]+", lower))
    found: set[str] = set()
    for bundle_id in all_bundle_ids():
        norm = bundle_id.lower()
        spaced = norm.replace("_", " ")
        if norm in lower or norm in tokens or spaced in lower:
            found.add(bundle_id)
    for alias, bundle_id in _DATASET_ALIASES.items():
        if alias in tokens or alias in lower:
            found.add(bundle_id)
    return tuple(sorted(found))


def excel_filename_for(bundle_ids: list[str], scenario: str) -> str:
    match = re.search(r"[\w.-]+\.xlsx", scenario, re.IGNORECASE)
    if match:
        return match.group(0)
    if len(bundle_ids) >= 2:
        left = bundle_ids[0].replace(_CSV_SUFFIX, "")
        right = bundle_ids[1].replace(_CSV_SUFFIX, "")
        return f"{left}_{right}_join.xlsx"
    only = bundle_ids[0].replace(_CSV_SUFFIX, "")
    return f"{only}_export.xlsx"


def _safe_node_id(bundle_id: str, suffix: str = "") -> str:
    base = re.sub(r"[^a-z0-9]+", "_", bundle_id.lower()).strip("_")
    return f"{base}{suffix}"


def build_single_bundle_excel_skeleton(bundle_id: str, filename: str) -> dict[str, Any]:
    load = build_load_spec(bundle_id)
    tab = bundle_id.replace(_CSV_SUFFIX, "")[:31]
    return {
        "workflow_id": f"blueprint-excel-{_safe_node_id(bundle_id)}",
        "name": f"Excel export: {bundle_id}",
        "description": f"Load {bundle_id} and export rows to Excel.",
        "nodes": [
            {"id": "start", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": "load",
                "type": load.node_type,
                "label": f"Load {bundle_id}",
                "config": load.config,
            },
            {
                "id": "export",
                "type": "excel_output",
                "label": "Excel workbook",
                "config": {"filename": filename, "tabNames": tab},
            },
        ],
        "edges": [
            {"from": "start", "to": "load"},
            {"from": "load", "to": "export"},
        ],
    }


def build_join_excel_skeleton(
    pair: JoinPairSpec,
    filename: str,
) -> dict[str, Any]:
    left_load = build_load_spec(pair.left_id)
    right_load = build_load_spec(pair.right_id)
    left_node = _safe_node_id(pair.left_id, "_load")
    right_node = _safe_node_id(pair.right_id, "_load")
    tab = f"{pair.left_id}_{pair.right_id}".replace(_CSV_SUFFIX, "")[:31]
    return {
        "workflow_id": f"blueprint-excel-{_safe_node_id(pair.left_id)}-{_safe_node_id(pair.right_id)}",
        "name": f"Excel join: {pair.left_id} + {pair.right_id}",
        "description": (
            f"Load {pair.left_id} and {pair.right_id}, join on "
            f"{pair.left_key}, export to Excel."
        ),
        "nodes": [
            {"id": "start", "type": "manual_trigger", "label": "Start", "config": {}},
            {
                "id": left_node,
                "type": left_load.node_type,
                "label": f"Load {pair.left_id}",
                "config": left_load.config,
            },
            {
                "id": right_node,
                "type": right_load.node_type,
                "label": f"Load {pair.right_id}",
                "config": right_load.config,
            },
            {
                "id": "join",
                "type": "join",
                "label": f"Join on {pair.left_key}",
                "config": {
                    "leftKey": pair.left_key,
                    "rightKey": pair.right_key,
                    "joinType": pair.join_type,
                },
            },
            {
                "id": "export",
                "type": "excel_output",
                "label": "Excel workbook",
                "config": {"filename": filename, "tabNames": tab},
            },
        ],
        "edges": [
            {"from": "start", "to": left_node},
            {"from": "start", "to": right_node},
            {"from": left_node, "to": "join"},
            {"from": right_node, "to": "join"},
            {"from": "join", "to": "export"},
        ],
    }
