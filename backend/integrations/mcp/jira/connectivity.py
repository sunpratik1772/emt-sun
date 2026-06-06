"""Jira Cloud REST connectivity — issues, comments, transitions."""
from __future__ import annotations

from typing import Any

from integrations.mcp.atlassian_transport import AtlassianTransport


class JiraClient:
    """Jira REST operations used by MCP tools."""

    def __init__(self, site_url: str, email: str, api_token: str) -> None:
        self._transport = AtlassianTransport(site_url, email, api_token)
        self.site_url = self._transport.site_url

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description_text: str,
        issue_type_name: str = "Task",
    ) -> dict[str, Any]:
        meta = self._transport.request(
            "GET",
            f"/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes",
        )
        issue_type_id = None
        for project in meta.get("projects", []):
            for it in project.get("issuetypes", []):
                if it.get("name", "").lower() == issue_type_name.lower():
                    issue_type_id = it["id"]
                    break
            if not issue_type_id and project.get("issuetypes"):
                issue_type_id = project["issuetypes"][0]["id"]
        if not issue_type_id:
            raise RuntimeError(f"No issue type found for project {project_key}")

        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"id": issue_type_id},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description_text[:32000]}],
                    }
                ],
            },
        }
        return self._transport.request("POST", "/rest/api/3/issue", json={"fields": fields})

    def add_comment(self, issue_key: str, body_text: str) -> dict[str, Any]:
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body_text[:32000]}],
                    }
                ],
            }
        }
        return self._transport.request("POST", f"/rest/api/3/issue/{issue_key}/comment", json=payload)

    def transition_issue(self, issue_key: str, transition_name: str = "Done") -> None:
        transitions = self._transport.request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
        tid = None
        for t in transitions.get("transitions", []):
            if t.get("name", "").lower() == transition_name.lower():
                tid = t["id"]
                break
        if not tid and transitions.get("transitions"):
            tid = transitions["transitions"][0]["id"]
        if not tid:
            return
        self._transport.request(
            "POST",
            f"/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": tid}},
        )

    def list_issues(self, *, jql: str, max_results: int = 20) -> dict[str, Any]:
        payload = {
            "jql": jql,
            "maxResults": max(1, min(int(max_results), 100)),
            "fields": ["summary", "status", "issuetype", "project", "assignee", "updated"],
        }
        return self._transport.request("POST", "/rest/api/3/search", json=payload)
