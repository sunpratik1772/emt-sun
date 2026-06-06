"""External integrations — MCP providers live under ``integrations/mcp/``."""
from integrations.mcp.registry import TOOL_ALIASES, get_tool, list_tools

__all__ = ["get_tool", "list_tools", "TOOL_ALIASES"]
