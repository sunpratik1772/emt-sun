"""MCP tool registry — maps tool names to provider handlers."""
from __future__ import annotations

import os
from typing import Any, Callable

from integrations.mcp.confluence.tools import CONFLUENCE_TOOLS
from integrations.mcp.credentials import resolve_atlassian, resolve_github
from integrations.mcp.github.tools import GITHUB_TOOLS
from integrations.mcp.jira.tools import JIRA_TOOLS

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

_LIVE_HANDLERS: dict[str, ToolFn] = {
    **CONFLUENCE_TOOLS,
    **JIRA_TOOLS,
    **GITHUB_TOOLS,
}

_ATLASSIAN_LIVE_TOOLS = frozenset({*CONFLUENCE_TOOLS.keys(), *JIRA_TOOLS.keys()})
_GITHUB_LIVE_TOOLS = frozenset(GITHUB_TOOLS.keys())

TOOL_ALIASES = {
    "create_confluence_page": "confluence_publish_report",
    "confluence_create_page": "confluence_publish_report",
    "publish_confluence_page": "confluence_publish_report",
}


def list_tools() -> list[str]:
    return sorted(_LIVE_HANDLERS.keys())


def get_tool(name: str) -> ToolFn | None:
    resolved = TOOL_ALIASES.get(name, name)
    return _LIVE_HANDLERS.get(resolved)


def _integration_name(params: dict[str, Any]) -> str:
    integration = str((params.get("_credentials") or {}).get("integration") or "atlassian").strip().lower()
    if integration == "studio_bridge":
        return "atlassian"
    return integration


def should_run_live(name: str, params: dict[str, Any]) -> bool:
    resolved = TOOL_ALIASES.get(name, name)
    if resolved not in _LIVE_HANDLERS:
        return False
    integration = _integration_name(params)
    if resolved in _ATLASSIAN_LIVE_TOOLS:
        if integration in {"github"}:
            return False
        atl = resolve_atlassian(params)
        return bool(atl["site_url"] and atl["email"] and atl["api_token"])
    if resolved in _GITHUB_LIVE_TOOLS:
        if integration in {"atlassian"}:
            return False
        gh = resolve_github(params)
        return bool(gh["token"] and gh["repo"])
    return False


def bridge_mode() -> str:
    return os.getenv("MCP_BRIDGE_MODE", "demo").strip().lower()
