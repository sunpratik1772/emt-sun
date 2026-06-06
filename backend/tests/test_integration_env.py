"""Mandatory integration env helpers."""
from __future__ import annotations

import pytest

from engine.integration_env import require_github_token, resolve_github_repo


def test_resolve_github_repo_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REPO", "acme/widgets")
    assert resolve_github_repo(None) == "acme/widgets"
    assert resolve_github_repo("your-github-repo-name") == "acme/widgets"
    assert resolve_github_repo("https://github.com/sunpratik1772/dbsherpa-studio") == "sunpratik1772/dbsherpa-studio"
    assert resolve_github_repo("https://github.com/sunpratik1772/dbsherpa-studio.git") == "sunpratik1772/dbsherpa-studio"
    assert resolve_github_repo("github.com/foo/bar") == "foo/bar"
    assert resolve_github_repo("dbsherpa-studio") == "acme/widgets"
    assert resolve_github_repo("owner/repository") == "acme/widgets"
    assert resolve_github_repo("https://github.com/your-username/your-repo") == "acme/widgets"


def test_require_github_token_accepts_either_name(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "pat-test")
    assert require_github_token() == "pat-test"
