"""
Copilot schema validation — orchestrator-backend parity.

Source: https://github.com/sunpratik1772/orchestrator-backend/blob/main/backend/engine/validator.py

Layer 4a of the self-healing pipeline calls this instead of
``engine.validator.validate_dag`` (Studio /run preflight). The orchestrator
validator is intentionally small: registry types, required config, edge
wiring, and branch sourceHandle rules — no surveillance legacy or orphan
false-positives on ``manual_trigger``.
"""
from __future__ import annotations

from typing import Any

from engine.registry import NODE_SPECS
from engine.studio_nodes import STUDIO_APPROVED_NODE_TYPES
from engine.validator import _is_entry_node_type


def _edge_endpoints(edge: dict) -> tuple[str | None, str | None]:
    return edge.get("source") or edge.get("from"), edge.get("target") or edge.get("to")


def _effective_config(config: dict[str, Any], params: tuple) -> dict[str, Any]:
    out = dict(config)
    for param in params:
        if param.name not in out and param.default is not None:
            out[param.name] = param.default
    return out


def _param_visible(param, config: dict[str, Any]) -> bool:
    if not getattr(param, "visible_if", None):
        return True
    for key, expected in param.visible_if.items():
        actual = config.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _missing_value(value: Any) -> bool:
    return value is None or value == "" or value == []


def validate_dag(nodes: list[dict], edges: list[dict]) -> str | None:
    """
    Return None if the workflow passes orchestrator schema checks, else a
    single human-readable traceback string (fed back to Gemini on repair).
    """
    valid_types = set(NODE_SPECS.keys())
    ids: set[str] = set()

    for n in nodes:
        nid = n.get("id")
        ntype = n.get("type")
        if ntype not in valid_types:
            return f"Node {nid!r} has unknown type {ntype!r}"
        if ntype not in STUDIO_APPROVED_NODE_TYPES:
            return (
                f"Node {nid!r} uses type {ntype!r} which is not in the Studio "
                f"palette. Use an approved node (agent, join, mcp, csv_extract, …)."
            )
        if not nid:
            return "Node is missing required field 'id'"
        if nid in ids:
            return f"Duplicate node id {nid!r}"
        ids.add(nid)

        spec = NODE_SPECS[ntype]
        cfg = n.get("config") or {}
        if not isinstance(cfg, dict):
            return f"Node {nid!r} ({ntype}) config must be an object"

        effective = _effective_config(cfg, spec.params)
        for param in spec.params:
            if not _param_visible(param, effective):
                continue
            if param.required and _missing_value(effective.get(param.name)):
                return (
                    f"Node {nid!r} ({ntype}) is missing required config "
                    f"field {param.name!r}"
                )
            value = effective.get(param.name)
            if getattr(param, "enum", None) and not _missing_value(value):
                if value not in param.enum:
                    return (
                        f"Node {nid!r} ({ntype}) config field {param.name!r} "
                        f"must be one of {list(param.enum)}, got {value!r}"
                    )

    by_src: dict[str, list[dict]] = {}
    for e in edges:
        src, tgt = _edge_endpoints(e)
        if src not in ids:
            return f"Edge {e.get('id')!r} references unknown source {src!r}"
        if tgt not in ids:
            return f"Edge {e.get('id')!r} references unknown target {tgt!r}"
        if src:
            by_src.setdefault(src, []).append(e)

    for n in nodes:
        nid = n["id"]
        ntype = n.get("type")
        outs = by_src.get(nid, [])
        if not outs:
            continue

        if ntype == "condition" and any(not e.get("sourceHandle") for e in outs):
            return (
                f"Condition node {nid!r} has outgoing edges without sourceHandle. "
                f"Each edge from a condition must set sourceHandle: 'true' or 'false'."
            )

        if ntype == "router":
            routes = (n.get("config") or {}).get("routes") or []
            labels = {
                str(r.get("label"))
                for r in routes
                if isinstance(r, dict) and r.get("label") is not None
            }
            if labels and any(not e.get("sourceHandle") for e in outs):
                return (
                    f"Router node {nid!r} has outgoing edges without sourceHandle. "
                    f"Each edge must set sourceHandle to a route label: {sorted(labels)!r}."
                )

    incoming: dict[str, int] = {nid: 0 for nid in ids}
    for e in edges:
        _, tgt = _edge_endpoints(e)
        if tgt in incoming:
            incoming[tgt] += 1

    for n in nodes:
        nid = n["id"]
        ntype = n.get("type")
        if _is_entry_node_type(ntype):
            continue
        if incoming.get(nid, 0) == 0:
            return (
                f"Node {nid!r} ({ntype}) has no incoming edge — wire it from an upstream node."
            )

    return None


def validate_workflow(workflow: dict) -> str | None:
    """Validate a copilot workflow dict (nodes + edges, any edge key style)."""
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    if not nodes:
        return "Workflow has zero nodes."
    return validate_dag(nodes, edges)
