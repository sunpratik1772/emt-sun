"""Shared join resolution for engine nodes and run replay."""
from __future__ import annotations

from typing import Any


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str | None, str | None]:
    src = edge.get("source") or edge.get("from")
    tgt = edge.get("target") or edge.get("to")
    return (str(src) if src is not None else None, str(tgt) if tgt is not None else None)


def _norm_port(raw: Any) -> str:
    handle = str(raw or "").strip().lower()
    if handle in ("left", "input1", "input_1", "in1"):
        return "left"
    if handle in ("right", "input2", "input_2", "in2"):
        return "right"
    return handle


def resolve_join_side_ids(
    node_id: str,
    incoming: dict[str, Any],
    edges: list[dict[str, Any]] | None,
) -> tuple[str | None, str | None]:
    """Map join node to left/right upstream ids using edge target handles."""
    left_id: str | None = None
    right_id: str | None = None
    fallback: list[str] = []

    for edge in edges or []:
        src, tgt = _edge_endpoints(edge)
        if tgt != node_id or not src or src not in incoming:
            continue
        port = _norm_port(edge.get("targetHandle") or edge.get("to_port"))
        if port == "left":
            left_id = src
        elif port == "right":
            right_id = src
        else:
            fallback.append(src)

    if left_id and right_id:
        return left_id, right_id

    ordered = fallback or sorted(incoming.keys())
    if len(ordered) >= 2:
        return ordered[0], ordered[1]
    if len(ordered) == 1:
        return ordered[0], None
    keys = sorted(incoming.keys())
    if len(keys) >= 2:
        return keys[0], keys[1]
    return (keys[0], None) if keys else (None, None)


def run_join_rows(
    node_id: str,
    incoming: dict[str, Any],
    cfg: dict[str, Any],
    edges: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Execute a join using config joinType and ordered left/right inputs.

    Returns (rows, meta) where meta includes joinType/keys echoed from config.
    """
    lk, rk = cfg.get("leftKey"), cfg.get("rightKey")
    jt = str(cfg.get("joinType") or "inner").lower()
    left_id, right_id = resolve_join_side_ids(node_id, incoming, edges)
    if not left_id or not right_id or left_id not in incoming or right_id not in incoming:
        return [], {"error": "Two upstream datasets and leftKey/rightKey required", "joinType": jt}
    if not lk or not rk:
        return [], {"error": "Two upstream datasets and leftKey/rightKey required", "joinType": jt}

    left = incoming[left_id].get("rows") or [] if isinstance(incoming[left_id], dict) else []
    right = incoming[right_id].get("rows") or [] if isinstance(incoming[right_id], dict) else []

    by_right: dict[Any, list[dict]] = {}
    for row in right:
        by_right.setdefault(row.get(rk), []).append(row)

    out: list[dict] = []
    matched_right: set[int] = set()
    for lrow in left:
        key_val = lrow.get(lk)
        matches = by_right.get(key_val, [])
        if matches:
            for rr in matches:
                out.append({**rr, **lrow})
                matched_right.add(id(rr))
        elif jt in ("left", "outer"):
            out.append(dict(lrow))

    if jt in ("right", "outer"):
        for rr in right:
            if id(rr) not in matched_right:
                out.append(dict(rr))

    meta = {
        "leftKey": lk,
        "rightKey": rk,
        "joinType": jt,
        "left_source": left_id,
        "right_source": right_id,
        "rowCount": len(out),
    }
    return out, meta
