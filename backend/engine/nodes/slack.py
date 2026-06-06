"""Slack send — requires SLACK_BOT_TOKEN or SLACK_WEBHOOK_URL."""
from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

import httpx

from ..context import RunContext
from ..integration_env import require_slack_auth
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def _upstream_rows(incoming):
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    channel = cfg.get("channel", "#general")
    rows = _upstream_rows(incoming)
    msg = cfg.get("message") or (
        f"New data: {_json.dumps(rows[0], default=str)[:200]}" if rows else "Workflow completed"
    )

    via, credential = require_slack_auth(cfg_webhook=cfg.get("webhookUrl"))

    if via == "bot_token":
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json; charset=utf-8"},
                json={"channel": channel, "text": msg},
            )
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if not body.get("ok"):
            raise RuntimeError(f"Slack API error: {body.get('error') or resp.text[:200]}")
        return {
            "sent": True,
            "via": "bot_token",
            "status": resp.status_code,
            "channel": channel,
            "ts": body.get("ts"),
            "rows": rows,
            "rowCount": len(rows),
        }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(credential, json={"text": msg, "channel": channel})
    if resp.status_code >= 400:
        raise RuntimeError(f"Slack webhook {resp.status_code}: {resp.text[:200]}")
    return {
        "sent": True,
        "via": "webhook",
        "status": resp.status_code,
        "channel": channel,
        "rows": rows,
        "rowCount": len(rows),
    }


NODE_SPEC = _spec_from_yaml(_HERE / "slack.yaml", run)
