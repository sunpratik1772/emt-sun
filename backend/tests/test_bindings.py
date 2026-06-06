"""Tests for engine.bindings — JSON templates and MCP row prep."""
from __future__ import annotations

from engine.bindings import (
    compile_workflow_bindings,
    prepare_mcp_rows,
    render_json_template,
    scan_rows_for_unresolved,
)


ROW = {"company": "Flux Media", "region": "MEA", "poem": "A bright future awaits."}


def test_render_json_template_nested() -> None:
    params = {
        "project": "DEMO",
        "summary": "Poem for {{row.company}}",
        "description": "{{poem}}",
    }
    out = render_json_template(params, ROW)
    assert out["summary"] == "Poem for Flux Media"
    assert out["description"] == "A bright future awaits."


def test_prepare_mcp_rows_jira_aliases() -> None:
    rows = [{"company": "Acme", "poem": "Hello world"}]
    params = {"project": "DEMO", "issue_type": "Task"}
    prepared = prepare_mcp_rows(rows, params, "jira_create_issue")
    assert prepared[0]["summary"] == "Acme"
    assert prepared[0]["description"] == "Hello world"
    assert prepared[0]["project"] == "DEMO"


def test_prepare_mcp_rows_renders_param_templates() -> None:
    rows = [{"company": "Acme", "poem": "Hello world"}]
    params = {
        "project": "DEMO",
        "summary": "Poem for {{company}}",
        "description": "{{row.poem}}",
    }
    prepared = prepare_mcp_rows(rows, params, "jira_create_issue")
    assert prepared[0]["summary"] == "Poem for Acme"
    assert prepared[0]["description"] == "Hello world"


def test_scan_rows_for_unresolved() -> None:
    rows = [{"poem": "Still {{row.company}} here"}]
    issues = scan_rows_for_unresolved(rows, ("poem",))
    assert len(issues) == 1


def test_compile_workflow_bindings_normalizes_mcp() -> None:
    wf = {
        "nodes": [
            {
                "id": "n9",
                "type": "mcp",
                "config": {
                    "tool": "jira_create_issue",
                    "params": {"description": "{{row.poem}}"},
                },
            }
        ],
        "edges": [],
    }
    compiled, notes = compile_workflow_bindings(wf)
    assert compiled["nodes"][0]["config"]["params"]["description"] == "{{poem}}"
    assert notes
