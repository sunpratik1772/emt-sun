"""Read rows from a registered mock dataset."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..context import RunContext
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent
  
from connectors.registry import get_rows


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    source = cfg.get("source") or ""
    rows = get_rows(source)
    limit = cfg.get("limit")
    if isinstance(limit, (int, float)) and int(limit) > 0:
        rows = rows[: int(limit)]
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    ctx.datasets["rows"] = df
    if source:
        ctx.datasets[str(source)] = df
    return {"source": source, "rows": rows, "rowCount": len(rows)}
  
NODE_SPEC = _spec_from_yaml(_HERE / "csv_extract.yaml", run)
  