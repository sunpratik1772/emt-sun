"""Shared Atlassian Cloud HTTP transport (Basic auth)."""
from __future__ import annotations

import base64
from typing import Any

import httpx


class AtlassianTransport:
    """Low-level REST transport for Atlassian Cloud APIs."""

    def __init__(self, site_url: str, email: str, api_token: str) -> None:
        if not all([site_url, email, api_token]):
            raise ValueError("Atlassian site_url, email, and api_token are required")
        normalized = site_url.strip()
        if not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"
        self.site_url = normalized.rstrip("/")
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = path if path.startswith("http") else f"{self.site_url}{path}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.request(method, url, headers=self._headers, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"Atlassian {resp.status_code}: {resp.text[:500]}")
        if resp.status_code == 204:
            return None
        return resp.json()
