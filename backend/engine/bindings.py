"""Unified row binding — string templates, JSON templates, MCP row prep."""
from __future__ import annotations

import json
import re
from typing import Any

from engine.mcp_contracts import McpToolContract, get_mcp_tool_contract
from engine.mcp_nodes import is_mcp_node_type
from .row_template import (
    contains_row_dot_placeholders,
    interpolate_row_template,
    normalize_row_dot_placeholders,
)

UNRESOLVED_PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")


def has_template_placeholders(value: Any) -> bool:
    if isinstance(value, str):
        return bool(UNRESOLVED_PLACEHOLDER_RE.search(value))
    if isinstance(value, dict):
        return any(has_template_placeholders(v) for v in value.values())
    if isinstance(value, list):
        return any(has_template_placeholders(v) for v in value)
    return False


def render_json_template(value: Any, row: dict[str, Any]) -> Any:
    """Recursively render ``{{field}}`` / ``{{row.field}}`` in strings inside JSON-like values."""
    if isinstance(value, str):
        return interpolate_row_template(value, row)
    if isinstance(value, list):
        return [render_json_template(item, row) for item in value]
    if isinstance(value, dict):
        return {k: render_json_template(v, row) for k, v in value.items()}
    return value


def apply_row_aliases(row: dict[str, Any], aliases: dict[str, str]) -> dict[str, Any]:
    out = dict(row)
    for src, dst in aliases.items():
        if src not in out:
            continue
        src_val = out.get(src)
        if dst not in out or not str(out.get(dst) or "").strip():
            out[dst] = src_val
    return out


def prepare_mcp_rows(
    rows: list[dict[str, Any]],
    params: dict[str, Any],
    tool: str,
) -> list[dict[str, Any]]:
    """Merge rendered param templates and tool aliases into each upstream row."""
    contract = get_mcp_tool_contract(tool)
    merge_keys = set(contract.merge_params if contract else params.keys())
    merge_keys.discard("data")

    prepared: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        for key in merge_keys:
            if key not in params:
                continue
            rendered = render_json_template(params[key], row)
            if isinstance(rendered, str) and rendered.strip():
                merged[key] = rendered
            elif not isinstance(rendered, str):
                merged[key] = rendered
        if contract:
            merged = apply_row_aliases(merged, contract.aliases)
        prepared.append(merged)
    return prepared


def scan_rows_for_unresolved(rows: list[dict[str, Any]], columns: tuple[str, ...] | None = None) -> list[str]:
    """Return human-readable issues for string cells that still contain placeholders."""
    issues: list[str] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        keys = columns or tuple(row.keys())
        for key in keys:
            val = row.get(key)
            if isinstance(val, str) and UNRESOLVED_PLACEHOLDER_RE.search(val):
                issues.append(
                    f"row {idx + 1} column '{key}' still contains unresolved placeholder: "
                    f"{val[:80]!r}"
                )
    return issues


def normalize_template_strings_in_value(value: Any) -> tuple[Any, bool]:
    """Normalize ``{{row.field}}`` → ``{{field}}`` in nested strings."""
    changed = False
    if isinstance(value, str):
        if contains_row_dot_placeholders(value):
            return normalize_row_dot_placeholders(value), True
        return value, False
    if isinstance(value, list):
        out_list = []
        for item in value:
            normalized, item_changed = normalize_template_strings_in_value(item)
            out_list.append(normalized)
            changed = changed or item_changed
        return out_list, changed
    if isinstance(value, dict):
        out_dict = {}
        for k, v in value.items():
            normalized, item_changed = normalize_template_strings_in_value(v)
            out_dict[k] = normalized
            changed = changed or item_changed
        return out_dict, changed
    return value, False


def compile_workflow_bindings(workflow: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Deterministic preflight pass: normalize agent/MCP templates in workflow JSON."""
    import copy

    dag = copy.deepcopy(workflow)
    notes: list[str] = []
    for node in dag.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        ntype = node.get("type")
        cfg = node.setdefault("config", {})
        if not isinstance(cfg, dict):
            continue
        node_id = node.get("id") or ntype

        if ntype == "agent":
            for key in ("prompt", "task", "rowTemplate"):
                val = cfg.get(key)
                if isinstance(val, str) and contains_row_dot_placeholders(val):
                    cfg[key] = normalize_row_dot_placeholders(val)
                    notes.append(f"{node_id}: agent.{key} normalized {{row.field}} → {{field}}")

        if is_mcp_node_type(ntype):
            params = cfg.get("params")
            if params is not None:
                normalized, changed = normalize_template_strings_in_value(params)
                if changed:
                    cfg["params"] = normalized
                    notes.append(f"{node_id}: mcp.params template placeholders normalized")

    return dag, notes
