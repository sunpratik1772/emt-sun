"""Locked MCP integration config — strip AI overrides, use .env at runtime."""
from __future__ import annotations

from engine.integration_locked import (
    strip_locked_mcp_config,
    MCP_LOCKED_CONFIG_KEYS,
)
from engine.nodes.mcp import _credentials_from_config
from copilot.workflow_finalize import finalize_workflow


def test_strip_locked_mcp_config_removes_credentials() -> None:
    wf = {
        "nodes": [
            {
                "id": "n04",
                "type": "mcp",
                "label": "MCP",
                "config": {
                    "integration": "confluence",
                    "tool": "confluence_publish_report",
                    "confluenceSpaceKey": "WRONG",
                    "confluenceApiToken": "secret",
                },
            }
        ],
        "edges": [],
    }
    out = strip_locked_mcp_config(wf)
    cfg = out["nodes"][0]["config"]
    assert "confluenceSpaceKey" not in cfg
    assert "confluenceApiToken" not in cfg
    assert cfg["tool"] == "confluence_publish_report"


def test_finalize_workflow_strips_mcp_credentials() -> None:
    wf = finalize_workflow(
        {
            "name": "W",
            "nodes": [
                {
                    "id": "n01",
                    "type": "mcp",
                    "config": {"confluenceSpaceKey": "NO_SUCH", "integration": "confluence", "tool": "x"},
                }
            ],
            "edges": [],
        }
    )
    assert "confluenceSpaceKey" not in wf["nodes"][0]["config"]


def test_credentials_from_config_ignores_canvas_values(monkeypatch) -> None:
    monkeypatch.setenv("CONFLUENCE_SPACE_KEY", "ENV_SPACE")
    monkeypatch.setenv("ATLASSIAN_SITE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("ATLASSIAN_EMAIL", "a@b.com")
    monkeypatch.setenv("ATLASSIAN_API_TOKEN", "tok")
    creds = _credentials_from_config(
        {"confluenceSpaceKey": "CANVAS_WRONG", "confluenceApiToken": "canvas-secret"}
    )
    assert creds["atlassian"]["confluence_space"] == "ENV_SPACE"
    assert creds["atlassian"]["api_token"] == "tok"
