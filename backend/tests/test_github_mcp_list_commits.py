"""Tests for github_mcp github_list_commits bridge tool and studio demo workflow."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine.copilot_validate import validate_dag_for_api
from engine.dag_runner import run_workflow
from mcp_bridge import tools

_BACKEND = Path(__file__).resolve().parent.parent
_STUDIO_17 = _BACKEND / "good_examples" / "studio_17_github_activity_briefing.json"


def test_github_list_commits_demo_mode_returns_fixture_rows(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_MODE", "demo")
    out = tools.run_tool(
        "github_list_commits",
        {"limit": 2},
        credentials={"integration": "github", "github": {"token": "demo", "repo": "demo-org/demo-app"}},
    )
    assert out["rowCount"] == 2
    assert out["mode"] == "demo"
    rows = out["rows"]
    assert rows[0]["message"]
    assert rows[0]["author"]
    assert rows[0]["commit_sha"]


def test_github_list_commits_live_normalizes_api_payload(monkeypatch) -> None:
    monkeypatch.setattr(tools, "_MODE", "live")
    fake_commits = [
        {
            "sha": "abc123def4567890",
            "html_url": "https://github.com/acme/app/commit/abc123",
            "author": {"login": "dev1"},
            "commit": {
                "message": "feat: ship github_list_commits\n\nBody",
                "author": {"name": "Dev One", "date": "2024-06-02T10:00:00Z"},
            },
        }
    ]
    mock_client = MagicMock()
    mock_client.list_commits.return_value = fake_commits

    with patch("integrations.mcp.github.tools.GitHubClient", return_value=mock_client):
        out = tools.run_tool(
            "github_list_commits",
            {"limit": 5, "repo": "acme/app"},
            credentials={"integration": "github", "github": {"token": "tok", "repo": "acme/app"}},
        )

    assert out["mode"] == "live"
    assert out["rowCount"] == 1
    row = out["rows"][0]
    assert row["repo"] == "acme/app"
    assert row["author"] == "dev1"
    assert row["message"] == "feat: ship github_list_commits"
    assert row["url"].endswith("/abc123")


def test_studio_17_validates() -> None:
    dag = json.loads(_STUDIO_17.read_text())
    result = validate_dag_for_api(dag)
    assert result.valid, [e.message for e in result.errors]


def test_studio_17_executes_with_demo_mcp_bridge(monkeypatch) -> None:
    dag = json.loads(_STUDIO_17.read_text())
    monkeypatch.setattr(tools, "_MODE", "demo")

    class _FakeResp:
        status_code = 200
        text = ""

        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def json(self):
            return self._payload

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            tool = str(url).split("/tools/")[1].split("/run")[0]
            body = json or {}
            result = tools.run_tool(
                tool,
                body.get("params") or {},
                credentials=body.get("credentials"),
            )
            return _FakeResp(result)

    with patch("engine.nodes.mcp_common.httpx.AsyncClient", _FakeAsyncClient):
        ctx = run_workflow(dag, {})

    commits = ctx.output_map.get("commits") or {}
    commit_rows = commits.get("rows") or []
    assert len(commit_rows) >= 1

    briefing = ctx.output_map.get("briefing") or {}
    summary_rows = briefing.get("rows") or []
    assert len(summary_rows) == 1
    assert "body_markdown" in summary_rows[0]
    assert "Recent commits" in summary_rows[0]["body_markdown"]

    publish = ctx.output_map.get("publish") or {}
    assert publish.get("rows") or publish.get("rowCount")


def test_active_mcp_tools_includes_github_list_commits() -> None:
    from engine.mcp_nodes import active_mcp_tools

    assert "github_list_commits" in active_mcp_tools()
