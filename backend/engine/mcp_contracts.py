"""MCP tool row contracts — expected bridge fields and column aliases."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class McpToolContract:
    tool: str
    description: str = ""
    required_row_fields: tuple[str, ...] = ()
    optional_row_fields: tuple[str, ...] = ()
    # Copy upstream column → bridge field when bridge field is empty.
    aliases: dict[str, str] = field(default_factory=dict)
    # Param keys that are merged onto each row (after template render).
    merge_params: tuple[str, ...] = ()


MCP_TOOL_CONTRACTS: dict[str, McpToolContract] = {
    "jira_create_issue": McpToolContract(
        tool="jira_create_issue",
        description="Create one Jira issue per upstream row.",
        required_row_fields=("summary",),
        optional_row_fields=("description", "project", "issue_type", "title", "body"),
        aliases={
            "poem": "description",
            "body": "description",
            "body_markdown": "description",
            "title": "summary",
            "company": "summary",
        },
        merge_params=("project", "issue_type", "summary", "description", "title", "body"),
    ),
    "confluence_publish_report": McpToolContract(
        tool="confluence_publish_report",
        required_row_fields=("title", "body_markdown"),
        optional_row_fields=("metrics_preview",),
        aliases={
            "pageTitle": "title",
            "body": "body_markdown",
            "content": "body_markdown",
        },
        merge_params=("title", "body_markdown", "pageTitle"),
    ),
    "tasks_bulk_create": McpToolContract(
        tool="tasks_bulk_create",
        optional_row_fields=("title", "summary", "status", "source_page_id"),
        aliases={"summary": "title"},
        merge_params=("title", "summary", "status"),
    ),
}


def get_mcp_tool_contract(tool: str) -> McpToolContract | None:
    return MCP_TOOL_CONTRACTS.get(tool)
