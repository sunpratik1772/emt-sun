#!/usr/bin/env python3
"""Normalize studio_*.json layouts: drop orphan notes, apply horizontal DAG layout."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

NODE_WIDTH = 240
COL_GAP = 56
COL_STRIDE = NODE_WIDTH + COL_GAP
ROW_HEIGHT = 132
CANVAS_PAD_X = 80
CANVAS_PAD_Y = 80
DEFAULT_CENTER_Y = CANVAS_PAD_Y + 200


def _build_graph(nodes: list[dict], edges: list[dict]):
    node_ids = [n["id"] for n in nodes]
    order_index = {nid: i for i, nid in enumerate(node_ids)}
    parents: dict[str, list[str]] = {nid: [] for nid in node_ids}
    children: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        src = e.get("from") or e.get("source")
        dst = e.get("to") or e.get("target")
        if src in parents and dst in children:
            parents[dst].append(src)
            children[src].append(dst)
    return node_ids, order_index, parents, children


def _compute_depths(node_ids, parents, children):
    indegree = {nid: len(parents[nid]) for nid in node_ids}
    depth = {nid: 0 for nid in node_ids}
    queue = [nid for nid in node_ids if indegree[nid] == 0]
    while queue:
        u = queue.pop(0)
        du = depth[u]
        for v in children[u]:
            depth[v] = max(depth[v], du + 1)
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    for _ in range(len(node_ids)):
        changed = False
        for nid in node_ids:
            if not parents[nid]:
                continue
            nxt = max(depth[p] for p in parents[nid]) + 1
            if depth[nid] < nxt:
                depth[nid] = nxt
                changed = True
        if not changed:
            break
    return depth


def _max_nodes_per_depth(node_ids, depth):
    counts: dict[int, int] = defaultdict(int)
    for nid in node_ids:
        counts[depth[nid]] += 1
    return max(counts.values(), default=0)


def _row_center_y(ids, parents, positions):
    parent_ys = []
    for nid in ids:
        for p in parents.get(nid, []):
            if p in positions:
                parent_ys.append(positions[p]["y"])
    if parent_ys:
        return sum(parent_ys) / len(parent_ys)
    return DEFAULT_CENTER_Y


def _sort_column_ids(ids, order_index, parents, positions):
    def key(nid):
        ps = parents.get(nid, [])
        if ps:
            bary = sum(positions.get(p, {}).get("y", DEFAULT_CENTER_Y) for p in ps) / len(ps)
        else:
            bary = DEFAULT_CENTER_Y
        return (bary, order_index.get(nid, 0))

    return sorted(ids, key=key)


def layout_workflow(nodes: list[dict], edges: list[dict]) -> dict[str, dict[str, float]]:
    node_ids, order_index, parents, children = _build_graph(nodes, edges)
    depth = _compute_depths(node_ids, parents, children)

    if _max_nodes_per_depth(node_ids, depth) == 1:
        # Topological order for linear chains
        indegree = {nid: len(parents[nid]) for nid in node_ids}
        ready = sorted([nid for nid in node_ids if indegree[nid] == 0], key=lambda i: order_index[i])
        ordered: list[str] = []
        while ready:
            u = ready.pop(0)
            ordered.append(u)
            for v in sorted(children[u], key=lambda i: order_index[i]):
                indegree[v] -= 1
                if indegree[v] == 0:
                    ready.append(v)
                    ready.sort(key=lambda i: order_index[i])
        if len(ordered) < len(node_ids):
            ordered = sorted(node_ids, key=lambda i: order_index[i])
        positions = {}
        for i, nid in enumerate(ordered):
            positions[nid] = {
                "x": CANVAS_PAD_X + i * COL_STRIDE,
                "y": DEFAULT_CENTER_Y,
            }
        return positions

    by_depth: dict[int, list[str]] = defaultdict(list)
    for nid in node_ids:
        by_depth[depth[nid]].append(nid)

    positions: dict[str, dict[str, float]] = {}
    for d in sorted(by_depth):
        ids = by_depth[d]
        x = CANVAS_PAD_X + d * COL_STRIDE
        sorted_ids = _sort_column_ids(ids, order_index, parents, positions)
        if len(sorted_ids) == 1:
            nid = sorted_ids[0]
            ps = parents.get(nid, [])
            y = DEFAULT_CENTER_Y
            if len(ps) == 1 and len(children.get(ps[0], [])) <= 1:
                y = positions.get(ps[0], {}).get("y", DEFAULT_CENTER_Y)
            elif ps:
                y = _row_center_y([nid], parents, positions)
            positions[nid] = {"x": x, "y": y}
            continue

        gap = ROW_HEIGHT
        stride = ROW_HEIGHT
        stack_height = (len(sorted_ids) - 1) * stride
        center_y = _row_center_y(sorted_ids, parents, positions)
        start_y = center_y - stack_height / 2
        for index, nid in enumerate(sorted_ids):
            positions[nid] = {"x": x, "y": start_y + index * stride}

    return positions


def normalize_dag(dag: dict) -> dict:
    nodes = [n for n in dag.get("nodes", []) if n.get("type") != "note"]
    edges = list(dag.get("edges") or [])

    # Merge note content into description (once).
    notes = [n for n in dag.get("nodes", []) if n.get("type") == "note"]
    if notes:
        extra = " ".join(
            (n.get("config") or {}).get("content", "").strip()
            for n in notes
            if (n.get("config") or {}).get("content", "").strip()
        )
        if extra:
            desc = (dag.get("description") or "").strip()
            if extra not in desc:
                dag["description"] = f"{desc} {extra}".strip() if desc else extra

    positions = layout_workflow(nodes, edges)
    for n in nodes:
        n["position"] = positions[n["id"]]

    out = dict(dag)
    out["nodes"] = nodes
    out["edges"] = edges
    return out


def main() -> None:
    good = Path(__file__).resolve().parents[1] / "good_examples"
    for path in sorted(good.glob("studio_*.json")):
        dag = json.loads(path.read_text(encoding="utf-8"))
        normalized = normalize_dag(dag)
        path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
        print(f"normalized {path.name}: {len(normalized['nodes'])} nodes")


if __name__ == "__main__":
    main()
