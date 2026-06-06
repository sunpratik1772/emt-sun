"""Legacy MCP Tool node — kept for saved workflows; prefer jira_mcp / confluence_mcp / github_mcp."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml
from .mcp_common import credentials_from_legacy_config, normalize_integration, run_mcp_bridge

_HERE = Path(__file__).parent


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    integration = normalize_integration(cfg.get("integration"))
    return await run_mcp_bridge(node, ctx, incoming, integration=integration)


# Re-export for tests and integration_locked
_credentials_from_config = credentials_from_legacy_config

NODE_SPEC = _spec_from_yaml(_HERE / "mcp.yaml", run)
