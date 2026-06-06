"""MCP integration package — one subpackage per provider."""
from integrations.mcp.credentials import resolve_atlassian, resolve_github
from integrations.mcp.registry import TOOL_ALIASES, get_tool, list_tools

__all__ = [
    "resolve_atlassian",
    "resolve_github",
    "get_tool",
    "list_tools",
    "TOOL_ALIASES",
]
