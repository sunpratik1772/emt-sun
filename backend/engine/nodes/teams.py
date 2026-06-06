"""Microsoft Teams message node — requires TEAMS_INCOMING_WEBHOOK_URL or webhookUrl."""
from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

import httpx

from ..context import RunContext
from ..integration_env import require_teams_webhook
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def _upstream_rows(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    rows = _upstream_rows(incoming)
    message = cfg.get("message") or (
        f"Workflow result: {_json.dumps(rows[0], default=str)[:900]}" if rows else "Workflow completed"
    )
    mode = str(cfg.get("deliveryMode") or "incoming_webhook")

    if mode == "graph":
        raise ValueError(
            "Teams Graph mode requires Azure app credentials (not yet supported). "
            "Use incoming_webhook mode with TEAMS_INCOMING_WEBHOOK_URL."
        )

    webhook = require_teams_webhook(cfg.get("webhookUrl"))

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(webhook, json={"text": message})
    if resp.status_code >= 400:
        raise RuntimeError(f"Teams webhook {resp.status_code}: {resp.text[:200]}")
    return {
        "sent": True,
        "via": "incoming_webhook",
        "status": resp.status_code,
        "message": message,
        "rows": rows,
        "rowCount": len(rows),
    }


NODE_SPEC = _spec_from_yaml(_HERE / "teams.yaml", run)
