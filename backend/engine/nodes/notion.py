"""Query a Notion database — requires NOTION_API_KEY."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from ..context import RunContext
from ..integration_env import require_notion
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    db_id = cfg.get("databaseId")
    if not db_id:
        raise ValueError("Notion node requires config.databaseId")
    api_key = require_notion()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=headers, json={})
    if resp.status_code >= 400:
        raise RuntimeError(f"Notion API {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    rows = [{"id": r.get("id"), **(r.get("properties") or {})} for r in data.get("results", [])]
    return {"rows": rows, "rowCount": len(rows), "hasMore": data.get("has_more", False)}


NODE_SPEC = _spec_from_yaml(_HERE / "notion.yaml", run)
