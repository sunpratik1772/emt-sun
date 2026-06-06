"""Integration nodes require real env credentials — no runtime stubs."""
from __future__ import annotations

import asyncio

import pytest

from engine.context import RunContext
from engine.integration_env import resolve_github_repo
from engine.nodes.github import run as github_run


def test_resolve_github_repo_uses_env_for_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REPO", "sunpratik1772/dbsherpa-studio")
    assert resolve_github_repo("your-github-repo-name") == "sunpratik1772/dbsherpa-studio"
    assert resolve_github_repo("") == "sunpratik1772/dbsherpa-studio"
    assert resolve_github_repo("other/repo") == "other/repo"


def test_resolve_github_repo_raises_when_missing(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    with pytest.raises(ValueError, match="GITHUB_REPO"):
        resolve_github_repo("your-github-repo-name")


def test_github_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    ctx = RunContext(alert_payload={})
    node = {
        "id": "gh1",
        "type": "github",
        "config": {"action": "create-issue", "repo": "owner/repo", "title": "t"},
    }
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        asyncio.run(github_run(node, ctx, {}))


def test_build_push_payload_resolves_node_csv_ref() -> None:
    from engine.nodes.github import _build_push_payload

    incoming = {
        "n03": {
            "csv": "id,name\n1,alpha\n",
            "rows": [{"id": 1, "name": "alpha"}],
            "rowCount": 1,
        }
    }
    cfg = {"fileContent": "{{n03.csv}}", "fileFormat": "csv"}
    assert _build_push_payload(cfg, incoming) == "id,name\n1,alpha\n"


def test_build_push_payload_falls_back_to_upstream_rows() -> None:
    from engine.nodes.github import _build_push_payload

    incoming = {
        "n03": {
            "rows": [{"id": 1, "name": "alpha"}],
            "rowCount": 1,
        }
    }
    cfg = {"fileFormat": "csv"}
    assert _build_push_payload(cfg, incoming) == "id,name\n1,alpha"
