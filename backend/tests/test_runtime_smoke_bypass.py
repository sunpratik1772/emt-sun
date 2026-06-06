"""Runtime smoke integration bypass — avoids repair loops on MCP/Jira errors."""
from __future__ import annotations

from generation.harness.runner import (
    _is_integration_smoke_error,
    _workflow_has_integration_nodes,
)


def test_integration_workflow_detection() -> None:
    wf = {"nodes": [{"type": "mcp"}, {"type": "db_query"}]}
    assert _workflow_has_integration_nodes(wf)
    assert not _workflow_has_integration_nodes({"nodes": [{"type": "filter"}]})


def test_jira_placeholder_error_is_integration() -> None:
    msg = 'MCP 500: mcp_bridge_error: No issue type found for project {{jiraProject}}'
    assert _is_integration_smoke_error(msg, {"nodes": [{"type": "mcp"}]})


def test_pure_dag_error_not_integration() -> None:
    msg = "output contract violated: node n3 missing rows input"
    assert not _is_integration_smoke_error(msg, {"nodes": [{"type": "join"}]})
