"""Telegram send — requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""
from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

import httpx

from ..context import RunContext
from ..integration_env import require_telegram
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def _upstream_rows(incoming):
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    parse_mode = cfg.get("parseMode") or "Markdown"
    rows = _upstream_rows(incoming)
    msg = cfg.get("message") or (
        f"New data: {_json.dumps(rows[0], default=str)[:200]}" if rows else "Workflow completed"
    )

    token, chat_id = require_telegram(cfg_token=cfg.get("botToken"), cfg_chat_id=cfg.get("chatId"))

    payload: dict[str, Any] = {"chat_id": chat_id, "text": msg}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body.get('description') or resp.text[:200]}")
    result = body.get("result") or {}
    return {
        "sent": True,
        "status": resp.status_code,
        "chatId": chat_id,
        "messageId": result.get("message_id"),
        "date": result.get("date"),
        "rows": rows,
        "rowCount": len(rows),
    }


NODE_SPEC = _spec_from_yaml(_HERE / "telegram.yaml", run)
