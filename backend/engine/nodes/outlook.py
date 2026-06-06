"""Outlook email via Microsoft Graph — requires OUTLOOK_* env vars."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..integration_env import require_outlook
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def _upstream_rows(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    rows = _upstream_rows(incoming)
    creds = require_outlook(cfg_tenant=cfg.get("tenantId"))
    # Real Graph send would use creds here once OAuth/token flow is wired.
    raise RuntimeError(
        "Outlook Graph send is not implemented yet. "
        f"Credentials present for tenant {creds['tenant_id'][:8]}… — wire Graph API next."
    )


NODE_SPEC = _spec_from_yaml(_HERE / "outlook.yaml", run)
