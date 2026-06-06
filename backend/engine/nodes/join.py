"""SQL-style join of two upstream datasets."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..join_utils import run_join_rows
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    node_id = str(node.get("id") or "")
    edges: list[dict] = getattr(ctx, "_active_edges", None) or []
    rows, meta = run_join_rows(node_id, incoming, cfg, edges)
    if meta.get("error"):
        return {"rows": [], "rowCount": 0, **meta}
    return {"rows": rows, **meta}

NODE_SPEC = _spec_from_yaml(_HERE / "join.yaml", run)
