"""Tests for copilot.binding_diagnosis."""
from __future__ import annotations

from copilot.binding_diagnosis import diagnose_binding_issues, format_binding_diagnosis_markdown


def test_diagnose_unresolved_placeholders_in_debug_json() -> None:
    payload = {
        "node_output": {
            "rows": [
                {
                    "company": "Flux Media",
                    "poem": "In {{row.region}}'s heart, {{row.company}} shines.",
                }
            ]
        }
    }
    issues = diagnose_binding_issues(debug_payload=payload)
    assert any(i["code"] == "UNRESOLVED_PLACEHOLDER" for i in issues)


def test_diagnose_mcp_missing_summary_field() -> None:
    workflow = {
        "nodes": [
            {
                "id": "n9",
                "type": "mcp",
                "config": {"tool": "jira_create_issue", "params": {"project": "DEMO"}},
            }
        ]
    }
    payload = {"node_output": {"rows": [{"poem": "Hello"}]}}
    issues = diagnose_binding_issues(workflow=workflow, debug_payload=payload)
    assert any(i["code"] == "MCP_MISSING_ROW_FIELD" for i in issues)


def test_format_binding_diagnosis_markdown() -> None:
    text = format_binding_diagnosis_markdown(
        [{"code": "TEST", "message": "Example", "fix": "Do the thing"}]
    )
    assert "Binding diagnosis" in text
    assert "Example" in text
