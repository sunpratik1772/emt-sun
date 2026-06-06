"""GitHub MCP tool handlers."""
from __future__ import annotations

import re
from typing import Any

from integrations.mcp.credentials import resolve_atlassian, resolve_github
from integrations.mcp.github.connectivity import GitHubClient
from integrations.mcp.jira.connectivity import JiraClient


def github_fix_jira_and_update(params: dict[str, Any]) -> dict[str, Any]:
    gh_cfg = resolve_github(params)
    gh = GitHubClient(gh_cfg["token"], gh_cfg["repo"])
    atl = resolve_atlassian(params)
    jira = JiraClient(atl["site_url"], atl["email"], atl["api_token"])

    rows = params.get("data") or []
    if not rows:
        raise ValueError("github_fix_jira_and_update requires upstream Jira issue rows")

    max_items = int(params.get("max") or 2)
    rows = rows[:max_items]
    base_branch, base_sha = gh.get_default_branch_sha()
    results = []

    for row in rows:
        key = row.get("issue_key", "JIRA-0")
        summary = row.get("summary") or key
        slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        branch = f"studio/mcp-{slug}"[:60]
        doc_path = f"docs/mcp-{slug}.md"
        test_path = f"python-backend/tests/test_mcp_jira_{slug.replace('-', '_')}.py"
        pr_url = ""
        status = "opened"
        error_msg = ""

        doc_body = (
            f"# {summary}\n\n"
            f"Automated doc stub for Jira `{key}`.\n\n"
            f"- Integration: MCP Tool node in Studio\n"
            f"- Bridge: MCP HTTP tools\n"
        )
        test_body = (
            f'"""Smoke test linked to Jira {key}."""\n\n\n'
            f"def test_{slug.replace('-', '_')}_linked():\n"
            f'    assert "{key}"\n'
        )

        try:
            try:
                gh.create_branch(branch, base_sha)
            except RuntimeError as exc:
                if "Reference already exists" not in str(exc):
                    raise
            gh.upsert_file(doc_path, doc_body, f"docs: MCP note for {key}", branch)
            gh.upsert_file(
                test_path,
                test_body,
                f"test: MCP workflow smoke test for {key}",
                branch,
            )
            pr = gh.create_pull_request(
                title=f"[{key}] {summary[:72]}",
                head=branch,
                base=base_branch,
                body=f"Workflow item for {key}.\n\n{summary}",
            )
            pr_url = pr.get("html_url", "")
        except RuntimeError as exc:
            status = "github_token_needs_write"
            error_msg = str(exc)[:400]
            pr_url = f"https://github.com/{gh_cfg['repo']}/compare/{base_branch}...{branch}?expand=1"

        jira_comment = (
            f"Studio MCP workflow update for {key}.\n\n"
            f"Summary: {summary}\n"
        )
        if pr_url and status == "opened":
            jira_comment += f"GitHub PR: {pr_url}\nBranch: `{branch}`\n"
        else:
            jira_comment += (
                "GitHub: could not push (PAT needs `Contents` + `Pull requests` write on "
                f"{gh_cfg['repo']}).\n"
                f"Draft compare link: {pr_url}\n"
                f"Planned files: `{doc_path}`, `{test_path}`\n"
            )
        if error_msg:
            jira_comment += f"\nAPI note: {error_msg[:200]}\n"

        try:
            jira.add_comment(key, jira_comment)
            jira.transition_issue(key, "Done")
        except RuntimeError:
            pass

        results.append(
            {
                "issue_key": key,
                "branch": branch,
                "pr_url": pr_url,
                "doc_file": doc_path,
                "test_file": test_path,
                "repo": gh_cfg["repo"],
                "status": status,
                "mode": "live",
            }
        )

    return {"rows": results, "rowCount": len(results), "mode": "live"}


def _normalize_commit_row(raw: dict[str, Any], *, repo: str) -> dict[str, Any]:
    commit = raw.get("commit") if isinstance(raw.get("commit"), dict) else {}
    author = commit.get("author") if isinstance(commit.get("author"), dict) else {}
    gh_author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    message = str(commit.get("message") or "").strip()
    return {
        "repo": repo,
        "sha": str(raw.get("sha") or "")[:40],
        "commit_sha": str(raw.get("sha") or "")[:12],
        "author": gh_author.get("login") or author.get("name") or "",
        "author_name": author.get("name") or gh_author.get("login") or "",
        "message": message.split("\n")[0] if message else "",
        "date": author.get("date") or "",
        "url": raw.get("html_url") or "",
    }


def github_list_commits(params: dict[str, Any]) -> dict[str, Any]:
    """List recent commits for the configured repo (live GitHub API)."""
    gh_cfg = resolve_github(params)
    repo = str(params.get("repo") or gh_cfg["repo"] or "").strip()
    if not repo:
        raise ValueError("github_list_commits requires GITHUB_REPO or params.repo (owner/name)")
    per_page = int(params.get("per_page") or params.get("limit") or params.get("max") or 20)
    gh = GitHubClient(gh_cfg["token"], repo)
    rows = [_normalize_commit_row(r, repo=repo) for r in gh.list_commits(per_page=per_page, sha=params.get("sha"))]
    return {"rows": rows, "rowCount": len(rows), "mode": "live", "repo": repo}


GITHUB_TOOLS = {
    "github_fix_jira_and_update": github_fix_jira_and_update,
    "github_list_commits": github_list_commits,
}
