"""Normalize Copilot-generated workflows for the Studio canvas."""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from engine.validator import _is_entry_node_type


def _normalize_workflow_for_validator(workflow: dict) -> dict:
    nodes = []
    for n in workflow.get("nodes") or []:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        nodes.append({
            "id": n["id"],
            "type": n["type"],
            "label": n.get("label") or n.get("type", "node"),
            "config": n.get("config") or {},
            **({"position": n["position"]} if n.get("position") else {}),
        })
    edges = []
    for e in workflow.get("edges") or []:
        if not isinstance(e, dict):
            continue
        src = e.get("from") or e.get("source")
        dst = e.get("to") or e.get("target")
        if not src or not dst:
            continue
        edge: dict[str, Any] = {"from": src, "to": dst}
        if e.get("sourceHandle"):
            edge["sourceHandle"] = e["sourceHandle"]
        edges.append(edge)
    return {
        "schema_version": "1.0",
        "workflow_id": workflow.get("workflow_id") or f"copilot-{int(time.time())}",
        "name": workflow.get("name") or "Untitled workflow",
        "version": workflow.get("version") or "1.0",
        "description": workflow.get("description") or "",
        "nodes": nodes,
        "edges": edges,
    }


def _repair_linear_edges(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Chain orphan nodes left-to-right when Copilot omits a wire."""
    if len(nodes) < 2:
        return edges

    by_id = {n["id"]: n for n in nodes if n.get("id")}
    sorted_ids = sorted(
        by_id,
        key=lambda i: float((by_id[i].get("position") or {}).get("x", 0)),
    )
    incoming: dict[str, int] = {nid: 0 for nid in by_id}
    existing: set[tuple[str, str]] = set()
    out: list[dict] = []

    for e in edges:
        src = e.get("from") or e.get("source")
        dst = e.get("to") or e.get("target")
        if not src or not dst or src not in by_id or dst not in by_id:
            continue
        out.append({"from": src, "to": dst, **(
            {"sourceHandle": e["sourceHandle"]} if e.get("sourceHandle") else {}
        )})
        existing.add((src, dst))
        incoming[dst] = incoming.get(dst, 0) + 1

    for i, nid in enumerate(sorted_ids):
        if i == 0:
            continue
        if incoming.get(nid, 0) > 0:
            continue
        if _is_entry_node_type(by_id[nid].get("type")):
            continue
        prev = sorted_ids[i - 1]
        if (prev, nid) not in existing:
            out.append({"from": prev, "to": nid})
            existing.add((prev, nid))
            incoming[nid] = incoming.get(nid, 0) + 1

    return out


def _repair_condition_source_handles(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Assign true/false handles when a condition node has unlabeled branch edges."""
    by_id = {n["id"]: n for n in nodes if n.get("id")}
    by_src: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        src = edge.get("from") or edge.get("source")
        if src:
            by_src[src].append(edge)

    for nid, node in by_id.items():
        if node.get("type") != "condition":
            continue
        outs = by_src.get(nid, [])
        missing = [e for e in outs if not e.get("sourceHandle")]
        if not missing:
            continue
        # Stable order: higher canvas Y first → "false" branch is often lower on canvas.
        def _target_y(edge: dict) -> float:
            tgt = edge.get("to") or edge.get("target")
            pos = (by_id.get(tgt or "", {}).get("position") or {}) if tgt else {}
            return float(pos.get("y", 0))

        missing.sort(key=_target_y)
        labels = ["true", "false"]
        for idx, edge in enumerate(missing):
            edge["sourceHandle"] = labels[idx] if idx < len(labels) else f"branch_{idx}"

    return edges


def finalize_workflow(workflow: dict) -> dict:
    """Validator-normalized workflow for the Studio canvas."""
    from engine.integration_locked import strip_locked_mcp_config

    dag = _normalize_workflow_for_validator(workflow)
    dag["edges"] = _repair_linear_edges(dag["nodes"], dag["edges"])
    dag["edges"] = _repair_condition_source_handles(dag["nodes"], dag["edges"])
    return strip_locked_mcp_config(dag)


def repair_workflow_for_run(workflow: dict) -> dict:
    """Apply deterministic repairs used by AutoFixer (tests / tooling)."""
    import copy

    from generation.repair.auto_fixer import AutoFixer
    from engine.copilot_validate import validate_dag_for_api

    validation = validate_dag_for_api(workflow)
    if validation.valid:
        return workflow
    candidate = copy.deepcopy(workflow)
    AutoFixer().fix(candidate, validation.to_json()["errors"])
    return candidate
