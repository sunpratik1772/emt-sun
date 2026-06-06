"""MCP tool handlers — demo fixtures plus optional live API passthrough."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from . import demo_data
from integrations.mcp.credentials import resolve_atlassian, resolve_github
from integrations.mcp.confluence.tools import CONFLUENCE_TOOLS
from integrations.mcp.github.tools import GITHUB_TOOLS
from integrations.mcp.jira.tools import JIRA_TOOLS
from integrations.mcp.registry import (
    TOOL_ALIASES as _TOOL_ALIASES,
    should_run_live as _should_run_live,
)

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]

_MODE = os.getenv("MCP_BRIDGE_MODE", "demo").strip().lower()

_LIVE_HANDLERS: dict[str, ToolFn] = {
    **CONFLUENCE_TOOLS,
    **JIRA_TOOLS,
    **GITHUB_TOOLS,
}

_ATLASSIAN_LIVE_TOOLS = frozenset({*CONFLUENCE_TOOLS.keys(), *JIRA_TOOLS.keys()})
_GITHUB_LIVE_TOOLS = frozenset(GITHUB_TOOLS.keys())


def _integration_name(params: dict[str, Any]) -> str:
    integration = str((params.get("_credentials") or {}).get("integration") or "atlassian").strip().lower()
    if integration == "studio_bridge":
        return "atlassian"
    return integration


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    return []


def _extract_action_items(text: str, source: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[-*]\s*\[\s*\]\s*(.+)$", line)
        if m:
            title = m.group(1).strip()
        elif line.lower().startswith("action:"):
            title = line.split(":", 1)[1].strip()
        else:
            continue
        items.append(
            {
                "task_id": f"TASK-{source.get('page_id', 'page')}-{len(items) + 1}",
                "title": title,
                "source_page_id": source.get("page_id"),
                "source_title": source.get("title"),
                "space": source.get("space"),
                "status": "open",
                "created_at": _now(),
            }
        )
    return items


def confluence_publish_report(params: dict[str, Any]) -> dict[str, Any]:
    """Demo: pretend to publish; uses upstream title/body_markdown when present."""
    upstream = _rows(params)
    first = upstream[0] if upstream else {}
    title = params.get("title") or first.get("title") or "Studio workflow analysis"
    space = (params.get("space") or first.get("space") or "ENG").upper()
    page_id = f"DEMO-{abs(hash(title)) % 90000 + 10000}"
    row = {
        "page_id": page_id,
        "title": title,
        "space": space,
        "url": f"https://demo.atlassian.net/wiki/spaces/{space}/pages/{page_id}",
        "mode": _MODE,
        "body_preview": (first.get("body_markdown") or params.get("body_markdown") or "")[:240],
    }
    return {"rows": [row], "rowCount": 1, "mode": _MODE}


def confluence_search_pages(params: dict[str, Any]) -> dict[str, Any]:
    space = (params.get("space") or "").upper()
    limit = int(params.get("limit") or 50)
    pages = demo_data.CONFLUENCE_PAGES
    if space:
        pages = [p for p in pages if p.get("space") == space]
    rows = pages[:limit]
    return {"rows": rows, "rowCount": len(rows), "mode": _MODE}


def confluence_extract_action_items(params: dict[str, Any]) -> dict[str, Any]:
    upstream = _rows(params)
    sources = upstream if upstream else demo_data.CONFLUENCE_PAGES
    tasks: list[dict[str, Any]] = []
    for page in sources:
        tasks.extend(_extract_action_items(page.get("body_excerpt", ""), page))
    if not tasks and params.get("page_id"):
        page = next((p for p in demo_data.CONFLUENCE_PAGES if p["page_id"] == params["page_id"]), None)
        if page:
            tasks = _extract_action_items(page.get("body_excerpt", ""), page)
    demo_data.TASKS_STORE.extend(tasks)
    return {"rows": tasks, "rowCount": len(tasks), "mode": _MODE}


def tasks_bulk_create(params: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(params)
    created = []
    for row in rows:
        task = {
            "task_id": row.get("task_id") or f"TASK-{len(demo_data.TASKS_STORE) + 1}",
            "title": row.get("title") or row.get("summary") or "Untitled",
            "status": row.get("status") or "open",
            "source_page_id": row.get("source_page_id"),
            "created_at": _now(),
        }
        demo_data.TASKS_STORE.append(task)
        created.append(task)
    return {"rows": created, "rowCount": len(created), "mode": _MODE}


def jira_create_issue(params: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(params)
    if not rows:
        rows = [
            {
                "project": params.get("project") or "DEMO",
                "summary": params.get("summary") or "Imported from Confluence",
                "description": params.get("description") or "",
                "issue_type": params.get("issue_type") or "Task",
            }
        ]
    created = []
    for i, row in enumerate(rows):
        key = f"DEMO-{100 + len(demo_data.JIRA_CREATED) + i}"
        issue = {
            "issue_key": key,
            "project": row.get("project") or params.get("project") or "DEMO",
            "summary": row.get("summary") or row.get("title") or "Untitled",
            "description": row.get("description") or row.get("body_excerpt") or "",
            "status": "To Do",
            "issue_type": row.get("issue_type") or "Task",
            "source_page_id": row.get("source_page_id") or row.get("page_id"),
            "created_at": _now(),
        }
        demo_data.JIRA_CREATED.append(issue)
        created.append(issue)
    return {"rows": created, "rowCount": len(created), "mode": _MODE}


def jira_list_issues(params: dict[str, Any]) -> dict[str, Any]:
    project = (params.get("project") or "").upper()
    status = params.get("status") or "To Do"
    max_items = int(params.get("max") or params.get("limit") or 10)
    issues = list(demo_data.JIRA_ISSUES) + list(demo_data.JIRA_CREATED)
    if project:
        issues = [i for i in issues if i.get("project", "").upper() == project]
    if status and status.lower() != "all":
        issues = [i for i in issues if i.get("status") == status]
    rows = issues[:max_items]
    return {"rows": rows, "rowCount": len(rows), "mode": _MODE}


def github_implement_fixes(params: dict[str, Any]) -> dict[str, Any]:
    """For each Jira issue row: simulate branch + test file + PR."""
    rows = _rows(params) or demo_data.JIRA_ISSUES[: int(params.get("max") or 3)]
    repo = params.get("repo") or os.getenv("GITHUB_REPO", "demo-org/demo-app")
    results = []
    for row in rows:
        key = row.get("issue_key", "DEMO-0")
        slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        branch = f"fix/{slug}"
        test_path = f"tests/test_{slug.replace('-', '_')}.py"
        test_body = (
            f'"""Auto-generated test for {key}: {row.get("summary", "")}"""\n\n'
            f"def test_{slug.replace('-', '_')}_smoke():\n"
            f'    assert True  # TODO: implement fix for {row.get("summary", "")}\n'
        )
        pr = {
            "issue_key": key,
            "repo": repo,
            "branch": branch,
            "test_file": test_path,
            "test_content": test_body,
            "pr_title": f"fix({key}): {row.get('summary', 'automated fix')}",
            "pr_url": f"https://github.com/{repo}/pull/{len(demo_data.GITHUB_ACTIVITY) + 1}",
            "status": "opened",
            "created_at": _now(),
        }
        demo_data.GITHUB_ACTIVITY.append(pr)
        results.append(pr)
    return {"rows": results, "rowCount": len(results), "mode": _MODE}


def github_list_commits(params: dict[str, Any]) -> dict[str, Any]:
    """Demo: return fixture commits for activity briefings."""
    repo = params.get("repo") or os.getenv("GITHUB_REPO", "demo-org/demo-app")
    max_items = int(params.get("per_page") or params.get("limit") or params.get("max") or 10)
    rows = [dict(r, repo=repo) for r in demo_data.GITHUB_COMMITS[:max_items]]
    return {"rows": rows, "rowCount": len(rows), "mode": _MODE, "repo": repo}


TOOL_REGISTRY: dict[str, ToolFn] = {
    "confluence_publish_report": confluence_publish_report,
    "confluence_search_pages": confluence_search_pages,
    "confluence_extract_action_items": confluence_extract_action_items,
    "tasks_bulk_create": tasks_bulk_create,
    "jira_create_issue": jira_create_issue,
    "jira_list_issues": jira_list_issues,
    "github_implement_fixes": github_implement_fixes,
    "github_list_commits": github_list_commits,
}


def list_tools() -> list[dict[str, str]]:
    names = sorted(set(TOOL_REGISTRY) | set(_LIVE_HANDLERS))
    out: list[dict[str, str]] = []
    for name in names:
        fn = _LIVE_HANDLERS.get(name) or TOOL_REGISTRY.get(name)
        if fn:
            out.append({"name": name, "description": fn.__doc__ or ""})
    return out


def run_tool(
    name: str,
    params: dict[str, Any],
    *,
    credentials: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = _TOOL_ALIASES.get(name, name)
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        raise KeyError(f"Unknown tool: {name}")
    payload = dict(params or {})
    if credentials:
        payload["_credentials"] = credentials

    if _MODE == "demo":
        return fn(payload)

    if _should_run_live(name, payload) and name in _LIVE_HANDLERS:
        return _LIVE_HANDLERS[name](payload)

    integration = _integration_name(payload)
    if name in _ATLASSIAN_LIVE_TOOLS:
        atl = resolve_atlassian(payload)
        missing = [k for k, v in (("ATLASSIAN_SITE_URL", atl["site_url"]), ("ATLASSIAN_EMAIL", atl["email"]), ("ATLASSIAN_API_TOKEN", atl["api_token"])) if not v]
        if missing:
            raise RuntimeError(
                f"MCP tool {name!r} requires live Atlassian credentials: {', '.join(missing)} in backend/.env"
            )
    if name in _GITHUB_LIVE_TOOLS:
        gh = resolve_github(payload)
        missing = [k for k, v in (("GITHUB_TOKEN", gh["token"]), ("GITHUB_REPO", gh["repo"])) if not v]
        if missing:
            raise RuntimeError(
                f"MCP tool {name!r} requires live GitHub credentials: {', '.join(missing)} in backend/.env"
            )

    raise RuntimeError(
        f"MCP tool {name!r} has no live implementation. Set MCP_BRIDGE_MODE=demo only for local fixture tests."
    )
