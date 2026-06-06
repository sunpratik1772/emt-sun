"""
orchestrator-backend node set (https://github.com/sunpratik1772/orchestrator-backend).

Studio palette handlers live under ``engine.nodes`` as paired YAML + Python modules.
"""
from __future__ import annotations

import importlib
from typing import Final

_MAIN_MODULE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "agent",
        "api_trigger",
        "code",
        "condition",
        "confluence_mcp",
        "csv_extract",
        "csv_output",
        "data_merge",
        "db_query",
        "deduplicate",
        "evaluator",
        "excel_output",
        "filter",
        "function",
        "github",
        "github_mcp",
        "group_by",
        "http",
        "join",
        "jira_mcp",
        "loop",
        "manual_trigger",
        "map_transform",
        "mcp",
        "note",
        "outlook",
        "pause",
        "pdf_extract",
        "response",
        "router",
        "schedule",
        "select_columns",
        "sort",
        "teams",
        "webhook_trigger",
    }
)


def __getattr__(name: str):
    if name in _MAIN_MODULE_NAMES:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
