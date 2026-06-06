"""Resolve credentials from MCP request payload or environment."""
from __future__ import annotations

import os
from typing import Any


def _normalize_site_url(raw: Any) -> str:
    value = str(raw or "").strip().strip("\"'")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value.rstrip("/")


def resolve_atlassian(params: dict[str, Any]) -> dict[str, str]:
    creds = (params.get("_credentials") or {}).get("atlassian") or {}
    return {
        "site_url": _normalize_site_url(
            creds.get("site_url") or os.getenv("ATLASSIAN_SITE_URL", "")
        ),
        "email": str(creds.get("email") or os.getenv("ATLASSIAN_EMAIL", "")),
        "api_token": str(creds.get("api_token") or os.getenv("ATLASSIAN_API_TOKEN", "")),
        "confluence_space": str(
            creds.get("confluence_space") or os.getenv("CONFLUENCE_SPACE_KEY", "MFS")
        ),
        "jira_project": str(creds.get("jira_project") or os.getenv("JIRA_PROJECT_KEY", "DEMO")),
    }


def resolve_github(params: dict[str, Any]) -> dict[str, str]:
    creds = (params.get("_credentials") or {}).get("github") or {}
    token = (
        creds.get("token")
        or os.getenv("GITHUB_TOKEN")
        or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        or ""
    )
    repo = str(creds.get("repo") or os.getenv("GITHUB_REPO", "sunpratik1772/dbsherpa-studio"))
    return {"token": str(token), "repo": repo}
