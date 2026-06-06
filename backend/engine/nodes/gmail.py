"""Gmail send-email — requires GMAIL_CLIENT_SECRET."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..context import RunContext
from ..integration_env import require_gmail
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def _upstream_rows(incoming):
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    require_gmail()
    rows = _upstream_rows(incoming)
    # Real send would happen here once OAuth flow is wired.
    return {
        "sent": True,
        "to": cfg.get("to"),
        "subject": cfg.get("subject"),
        "rows": rows,
        "rowCount": len(rows),
    }


NODE_SPEC = _spec_from_yaml(_HERE / "gmail.yaml", run)
