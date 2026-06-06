"""Integration credential fields — locked to backend/.env, not AI or canvas edits."""
from __future__ import annotations

import copy
import os
from typing import Any

from runtime_env import ensure_env_loaded

from .mcp_nodes import MCP_NODE_TYPES, is_mcp_node_type

# MCP node config keys that must never be persisted or honored from workflow JSON.
MCP_LOCKED_CONFIG_KEYS: frozenset[str] = frozenset({
    "jiraSiteUrl",
    "jiraEmail",
    "jiraApiToken",
    "jiraProjectKey",
    "confluenceSiteUrl",
    "confluenceEmail",
    "confluenceApiToken",
    "confluenceSpaceKey",
    "githubToken",
    "githubRepo",
    "atlassianSiteUrl",
    "atlassianEmail",
    "atlassianApiToken",
})

MCP_CONFIG_KEY_TO_ENV: dict[str, str] = {
    "jiraSiteUrl": "ATLASSIAN_SITE_URL",
    "confluenceSiteUrl": "ATLASSIAN_SITE_URL",
    "atlassianSiteUrl": "ATLASSIAN_SITE_URL",
    "jiraEmail": "ATLASSIAN_EMAIL",
    "confluenceEmail": "ATLASSIAN_EMAIL",
    "atlassianEmail": "ATLASSIAN_EMAIL",
    "jiraApiToken": "ATLASSIAN_API_TOKEN",
    "confluenceApiToken": "ATLASSIAN_API_TOKEN",
    "atlassianApiToken": "ATLASSIAN_API_TOKEN",
    "confluenceSpaceKey": "CONFLUENCE_SPACE_KEY",
    "jiraProjectKey": "JIRA_PROJECT_KEY",
    "githubToken": "GITHUB_TOKEN",
    "githubRepo": "GITHUB_REPO",
}

_SECRET_CONFIG_KEYS: frozenset[str] = frozenset({
    "jiraApiToken",
    "confluenceApiToken",
    "atlassianApiToken",
    "githubToken",
})


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return "(not set in backend/.env)"
    if len(v) <= 8:
        return "••••••••"
    return f"{v[:4]}…{v[-4:]}"


def integration_env_defaults_for_ui() -> dict[str, Any]:
    """Values for locked inspector fields (secrets masked)."""
    ensure_env_loaded()
    mcp: dict[str, str] = {}
    for cfg_key, env_name in MCP_CONFIG_KEY_TO_ENV.items():
        raw = (os.getenv(env_name) or "").strip()
        if cfg_key.endswith("ApiToken") or cfg_key == "githubToken":
            mcp[cfg_key] = _mask_secret(raw)
        else:
            mcp[cfg_key] = raw or "(not set in backend/.env)"
    return {
        "mcp": mcp,
        "env_keys": dict(MCP_CONFIG_KEY_TO_ENV),
        "locked_keys": sorted(MCP_LOCKED_CONFIG_KEYS),
    }


def strip_locked_mcp_config(workflow: dict[str, Any]) -> dict[str, Any]:
    """Remove env-backed credential keys from MCP nodes (AI/history cannot override .env)."""
    out = copy.deepcopy(workflow)
    for node in out.get("nodes") or []:
        if not isinstance(node, dict) or not is_mcp_node_type(node.get("type")):
            continue
        cfg = node.get("config")
        if not isinstance(cfg, dict):
            continue
        for key in MCP_LOCKED_CONFIG_KEYS:
            cfg.pop(key, None)
    return out
