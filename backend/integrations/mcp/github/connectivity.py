"""GitHub REST connectivity — branches, files, pull requests."""
from __future__ import annotations

import base64
import os
import subprocess
from typing import Any

import httpx


def _resolve_github_token(explicit: str) -> str:
    if explicit:
        return explicit
    env_tok = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or ""
    if env_tok:
        return env_tok
    try:
        return subprocess.check_output(
            ["env", "-u", "GITHUB_TOKEN", "gh", "auth", "token"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


class GitHubClient:
    """GitHub REST client for branch, file, and PR operations."""

    def __init__(self, token: str, repo: str) -> None:
        token = _resolve_github_token(token)
        if not token:
            raise ValueError("GitHub token is required (GITHUB_TOKEN or `gh auth login`)")
        owner, _, name = repo.partition("/")
        if not owner or not name:
            raise ValueError(f"Invalid repo {repo!r}; expected owner/name")
        self.repo = f"{owner}/{name}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"https://api.github.com/repos/{self.repo}{path}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.request(method, url, headers=self._headers, **kwargs)
        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub {resp.status_code}: {resp.text[:500]}")
        if resp.status_code == 204:
            return None
        return resp.json()

    def get_repo(self) -> dict[str, Any]:
        return self._request("GET", "")

    def get_default_branch_sha(self) -> tuple[str, str]:
        repo = self.get_repo()
        branch = repo.get("default_branch") or "main"
        ref = self._request("GET", f"/git/ref/heads/{branch}")
        return branch, ref["object"]["sha"]

    def create_branch(self, branch: str, from_sha: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )

    def upsert_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict[str, Any]:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        body: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        try:
            existing = self._request("GET", f"/contents/{path}?ref={branch}")
            body["sha"] = existing["sha"]
        except RuntimeError:
            pass
        return self._request("PUT", f"/contents/{path}", json=body)

    def create_pull_request(
        self,
        title: str,
        head: str,
        base: str,
        body: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
        )

    def list_commits(self, *, per_page: int = 30, sha: str | None = None) -> list[dict[str, Any]]:
        per_page = max(1, min(int(per_page or 30), 100))
        query = f"per_page={per_page}"
        if sha:
            query += f"&sha={sha}"
        data = self._request("GET", f"/commits?{query}")
        if not isinstance(data, list):
            return []
        return [r for r in data if isinstance(r, dict)]
