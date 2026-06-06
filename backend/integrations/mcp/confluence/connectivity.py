"""Confluence Cloud REST connectivity — pages and spaces."""
from __future__ import annotations

from typing import Any

from integrations.mcp.atlassian_transport import AtlassianTransport


class ConfluenceClient:
    """Confluence REST operations used by MCP tools."""

    def __init__(self, site_url: str, email: str, api_token: str) -> None:
        self._transport = AtlassianTransport(site_url, email, api_token)
        self.site_url = self._transport.site_url

    def create_page(self, space_key: str, title: str, html_body: str) -> dict[str, Any]:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {"value": html_body, "representation": "storage"},
            },
        }
        return self._transport.request("POST", "/wiki/rest/api/content", json=payload)

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._transport.request(
            "GET",
            f"/wiki/rest/api/content/{page_id}?expand=body.storage,space",
        )
