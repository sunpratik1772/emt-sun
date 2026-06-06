"""GitHub MCP node — bridge tools for fix branches and Jira-linked PRs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml
from .mcp_common import run_mcp_bridge

_HERE = Path(__file__).parent

_INTEGRATION = "github"


async def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    return await run_mcp_bridge(node, ctx, incoming, integration=_INTEGRATION)


NODE_SPEC = _spec_from_yaml(_HERE / "github_mcp.yaml", run)
