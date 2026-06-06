"""Jira MCP tool handlers."""
from __future__ import annotations

import re
from typing import Any

from integrations.mcp.confluence.connectivity import ConfluenceClient
from integrations.mcp.credentials import resolve_atlassian
from integrations.mcp.jira.connectivity import JiraClient


def jira_create_epics_from_confluence(params: dict[str, Any]) -> dict[str, Any]:
    atl = resolve_atlassian(params)
    jira = JiraClient(atl["site_url"], atl["email"], atl["api_token"])
    conf = ConfluenceClient(atl["site_url"], atl["email"], atl["api_token"])
    upstream = params.get("data") or []
    page_id = params.get("page_id")
    if not page_id and upstream:
        page_id = upstream[0].get("page_id")
    if not page_id:
        raise ValueError("jira_create_epics_from_confluence requires page_id or upstream row with page_id")

    page = conf.get_page(str(page_id))
    page_title = page.get("title", "Architecture doc")
    body = ((page.get("body") or {}).get("storage") or {}).get("value", "")
    plain = re.sub(r"<[^>]+>", " ", body)
    plain = re.sub(r"\s+", " ", plain).strip()[:2000]

    tasks = [
        (
            "[Tech] Document MCP bridge HTTP contract",
            f"From Confluence page {page_id}: define /tools/{{name}}/run and credential passthrough.",
        ),
        (
            "[Tech] Wire Studio MCP node credentials UI",
            f"From Confluence page {page_id}: integration dropdown + masked tokens in inspector.",
        ),
    ]
    created = []
    for summary, desc in tasks:
        issue = jira.create_issue(
            atl["jira_project"],
            summary,
            f"{desc}\n\nSource: {page_title}\n\n{plain[:1500]}",
            issue_type_name=params.get("issue_type") or "Task",
        )
        key = issue.get("key", "")
        created.append(
            {
                "issue_key": key,
                "summary": summary,
                "project": atl["jira_project"],
                "status": "To Do",
                "confluence_page_id": page_id,
                "url": f"{atl['site_url']}/browse/{key}",
                "mode": "live",
            }
        )
    return {"rows": created, "rowCount": len(created), "mode": "live"}


def jira_create_issue(params: dict[str, Any]) -> dict[str, Any]:
    atl = resolve_atlassian(params)
    client = JiraClient(atl["site_url"], atl["email"], atl["api_token"])
    rows = params.get("data") or []
    if not rows:
        rows = [
            {
                "project": params.get("project") or atl["jira_project"],
                "summary": params.get("summary") or "Imported issue",
                "description": params.get("description") or "",
                "issue_type": params.get("issue_type") or "Task",
            }
        ]

    created: list[dict[str, Any]] = []
    for row in rows:
        project = row.get("project") or params.get("project") or atl["jira_project"]
        summary = row.get("summary") or row.get("title") or "Imported issue"
        description = row.get("description") or row.get("body_excerpt") or ""
        issue_type = row.get("issue_type") or params.get("issue_type") or "Task"
        issue = client.create_issue(
            str(project),
            str(summary),
            str(description),
            issue_type_name=str(issue_type),
        )
        key = issue.get("key", "")
        created.append(
            {
                "issue_key": key,
                "project": project,
                "summary": summary,
                "status": "To Do",
                "issue_type": issue_type,
                "url": f"{atl['site_url']}/browse/{key}" if key else "",
                "mode": "live",
            }
        )
    return {"rows": created, "rowCount": len(created), "mode": "live"}


def jira_list_issues(params: dict[str, Any]) -> dict[str, Any]:
    atl = resolve_atlassian(params)
    client = JiraClient(atl["site_url"], atl["email"], atl["api_token"])
    project = str(params.get("project") or atl["jira_project"] or "").strip().upper()
    status = str(params.get("status") or "").strip()
    limit = int(params.get("max") or params.get("limit") or 20)

    jql = str(params.get("jql") or "").strip()
    if not jql:
        clauses: list[str] = []
        if project:
            clauses.append(f'project = "{project}"')
        if status and status.lower() != "all":
            clauses.append(f'status = "{status}"')
        jql = " AND ".join(clauses) if clauses else "ORDER BY updated DESC"
        if "ORDER BY" not in jql.upper():
            jql = f"{jql} ORDER BY updated DESC"

    payload = client.list_issues(jql=jql, max_results=limit)
    rows: list[dict[str, Any]] = []
    for issue in payload.get("issues", []) or []:
        fields = issue.get("fields") or {}
        issue_type = fields.get("issuetype") or {}
        status_obj = fields.get("status") or {}
        project_obj = fields.get("project") or {}
        assignee_obj = fields.get("assignee") or {}
        key = issue.get("key") or ""
        rows.append(
            {
                "issue_key": key,
                "summary": fields.get("summary") or "",
                "project": project_obj.get("key") or project,
                "status": status_obj.get("name") or "",
                "issue_type": issue_type.get("name") or "",
                "assignee": assignee_obj.get("displayName") or "",
                "updated": fields.get("updated") or "",
                "url": f"{atl['site_url']}/browse/{key}" if key else "",
                "mode": "live",
            }
        )
    return {"rows": rows, "rowCount": len(rows), "mode": "live"}


JIRA_TOOLS = {
    "jira_create_epics_from_confluence": jira_create_epics_from_confluence,
    "jira_create_issue": jira_create_issue,
    "jira_list_issues": jira_list_issues,
}
