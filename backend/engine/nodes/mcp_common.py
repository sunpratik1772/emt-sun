"""Shared MCP bridge helpers for jira_mcp, confluence_mcp, github_mcp, and legacy mcp nodes."""
from __future__ import annotations

import json as _json
import logging
import os
from typing import Any

import httpx
from runtime_env import ensure_env_loaded

from engine.mcp_nodes import resolve_mcp_tool
from ..bindings import prepare_mcp_rows, scan_rows_for_unresolved
from ..context import RunContext

ensure_env_loaded()

logger = logging.getLogger(__name__)

_DEFAULT_BRIDGE = "http://127.0.0.1:8765"
_TIMEOUT_S = float(os.getenv("MCP_HTTP_TIMEOUT", "120"))


def upstream_rows(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def env_or_default(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def atlassian_credentials() -> dict[str, str]:
    return {
        "site_url": env_or_default("ATLASSIAN_SITE_URL"),
        "email": env_or_default("ATLASSIAN_EMAIL"),
        "api_token": env_or_default("ATLASSIAN_API_TOKEN"),
        "confluence_space": env_or_default("CONFLUENCE_SPACE_KEY", "MFS"),
        "jira_project": env_or_default("JIRA_PROJECT_KEY", "DEMO"),
    }


def github_credentials() -> dict[str, str]:
    token = env_or_default("GITHUB_TOKEN") or env_or_default("GITHUB_PERSONAL_ACCESS_TOKEN")
    repo = env_or_default("GITHUB_REPO")
    if repo:
        try:
            from ..integration_env import resolve_github_repo

            repo = resolve_github_repo(repo)
        except Exception:
            pass
    return {"token": token, "repo": repo}


def credentials_payload(*, integration: str) -> dict[str, Any]:
    """Credentials always come from backend/.env — workflow config cannot override."""
    normalized = integration.strip().lower()
    if normalized in {"github", "git"}:
        return {"integration": "github", "github": github_credentials()}
    return {
        "integration": "atlassian",
        "atlassian": atlassian_credentials(),
    }


def normalize_integration(value: Any) -> str:
    integration = str(value or "atlassian").strip().lower()
    if integration in ("jira", "confluence", "atlassian", "studio_bridge"):
        return "atlassian"
    if integration in ("github", "git"):
        return "github"
    return integration


def credentials_from_legacy_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Legacy mcp node — infer integration from config.integration."""
    integration = normalize_integration(cfg.get("integration"))
    atl = atlassian_credentials()
    gh = github_credentials()
    return {
        "integration": integration,
        "atlassian": atl,
        "github": gh,
    }


def bridge_url(cfg: dict[str, Any]) -> str:
    return str(
        cfg.get("serverUrl")
        or os.getenv("MCP_SERVER_URL")
        or os.getenv("MCP_BRIDGE_URL")
        or _DEFAULT_BRIDGE
    ).rstrip("/")


def resolve_tool(raw: Any) -> str:
    name = str(raw or "").strip()
    return resolve_mcp_tool(name)


async def run_mcp_bridge(
    node: dict,
    ctx: RunContext,
    incoming: dict[str, Any],
    *,
    integration: str,
    default_tool: str = "",
) -> dict[str, Any]:
    cfg = node.get("config") or {}
    tool = resolve_tool(cfg.get("tool") or default_tool)
    if not tool:
        raise ValueError(f"{node.get('type')} node requires config.tool")

    try:
        from app.mcp_lifecycle import ensure_mcp_bridge

        ensure_mcp_bridge()
    except Exception:
        pass

    server = bridge_url(cfg)
    rows = upstream_rows(incoming)
    raw = cfg.get("params")
    params = raw if isinstance(raw, dict) else (_json.loads(raw) if raw else {})
    if rows:
        prepared = prepare_mcp_rows(rows, params, tool)
        unresolved = scan_rows_for_unresolved(prepared)
        if unresolved:
            logger.warning(
                "MCP node %s (%s): unresolved placeholders after render: %s",
                node.get("id"),
                tool,
                unresolved[:3],
            )
        params["data"] = prepared
    if cfg.get("pageTitle"):
        params["title"] = cfg["pageTitle"]

    body = {
        "params": params,
        "credentials": credentials_payload(integration=integration),
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
        resp = await client.post(f"{server}/tools/{tool}/run", json=body)
    if resp.status_code >= 400:
        detail = resp.text[:400]
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                detail = str(payload.get("detail") or payload)
        except Exception:
            pass
        raise RuntimeError(f"MCP {resp.status_code}: {detail[:400]}")

    data = resp.json()
    if isinstance(data, list):
        out_rows = data
    elif isinstance(data, dict) and isinstance(data.get("rows"), list):
        out_rows = data["rows"]
    else:
        out_rows = [data] if isinstance(data, dict) else []
    return {
        "tool": tool,
        "integration": normalize_integration(integration),
        "rows": out_rows,
        "rowCount": len(out_rows),
        "bridge": server,
    }
