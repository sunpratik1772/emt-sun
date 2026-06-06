"""Single source of truth for MCP node types, tools, and workflow helpers."""
from __future__ import annotations

from typing import Any

TOOL_ALIASES: dict[str, str] = {
    "create_confluence_page": "confluence_publish_report",
    "confluence_create_page": "confluence_publish_report",
    "publish_confluence_page": "confluence_publish_report",
}

MCP_NODE_TYPES: frozenset[str] = frozenset({
    "mcp",
    "jira_mcp",
    "confluence_mcp",
    "github_mcp",
})

JIRA_MCP_TOOLS: frozenset[str] = frozenset({
    "jira_create_issue",
    "jira_list_issues",
    "jira_create_epics_from_confluence",
    "tasks_bulk_create",
})

CONFLUENCE_MCP_TOOLS: frozenset[str] = frozenset({
    "confluence_search_pages",
    "confluence_extract_action_items",
    "confluence_publish_report",
    "studio_publish_architecture_doc",
})

GITHUB_MCP_TOOLS: frozenset[str] = frozenset({
    "github_list_commits",
    "github_implement_fixes",
    "github_fix_jira_and_update",
})

ALL_MCP_TOOLS: frozenset[str] = JIRA_MCP_TOOLS | CONFLUENCE_MCP_TOOLS | GITHUB_MCP_TOOLS

MCP_NODE_TYPE_BY_INTEGRATION: dict[str, str] = {
    "jira": "jira_mcp",
    "confluence": "confluence_mcp",
    "github": "github_mcp",
    "git": "github_mcp",
    "atlassian": "jira_mcp",
}


def resolve_mcp_tool(tool: str) -> str:
    name = str(tool or "").strip()
    return TOOL_ALIASES.get(name, name)


def is_mcp_node_type(type_id: str | None) -> bool:
    return str(type_id or "").strip().lower() in MCP_NODE_TYPES


def mcp_node_type_for_tool(tool: str) -> str:
    resolved = resolve_mcp_tool(tool)
    if resolved in JIRA_MCP_TOOLS:
        return "jira_mcp"
    if resolved in CONFLUENCE_MCP_TOOLS:
        return "confluence_mcp"
    if resolved in GITHUB_MCP_TOOLS:
        return "github_mcp"
    return "mcp"


def mcp_integration_for_node_type(type_id: str) -> str:
    tid = str(type_id or "").strip().lower()
    if tid == "github_mcp":
        return "github"
    if tid in {"jira_mcp", "confluence_mcp", "mcp"}:
        return "atlassian"
    return "atlassian"


def active_mcp_node_types() -> tuple[str, ...]:
    from .registry import all_specs

    return tuple(
        sorted(s.type_id for s in all_specs() if s.type_id in MCP_NODE_TYPES and s.type_id != "mcp")
    )


def active_mcp_tools() -> tuple[str, ...]:
    return tuple(sorted(ALL_MCP_TOOLS))


def normalize_mcp_node(node: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy ``mcp`` nodes to typed jira/confluence/github_mcp nodes."""
    if not isinstance(node, dict):
        return node
    ntype = str(node.get("type") or "")
    cfg = dict(node.get("config") or {})
    if ntype == "mcp":
        tool = str(cfg.get("tool") or "")
        ntype = mcp_node_type_for_tool(tool)
    cfg.pop("integration", None)
    return {**node, "type": ntype, "config": cfg}


def normalize_mcp_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    nodes = workflow.get("nodes") or []
    if not isinstance(nodes, list):
        return workflow
    out_nodes = [
        normalize_mcp_node(n) if isinstance(n, dict) else n
        for n in nodes
    ]
    return {**workflow, "nodes": out_nodes}


def workflow_uses_mcp(workflow: dict[str, Any] | None) -> bool:
    if not workflow:
        return False
    for node in workflow.get("nodes") or []:
        if isinstance(node, dict) and is_mcp_node_type(node.get("type")):
            return True
    return False
