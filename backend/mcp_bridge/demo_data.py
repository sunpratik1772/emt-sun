"""Fixture data for MCP bridge demo mode (no live Atlassian/GitHub credentials)."""
from __future__ import annotations

CONFLUENCE_PAGES = [
    {
        "page_id": "CONF-101",
        "title": "Q2 Platform rollout checklist",
        "space": "ENG",
        "url": "https://demo.atlassian.net/wiki/spaces/ENG/pages/101",
        "labels": ["checklist", "platform"],
        "body_excerpt": "- [ ] Migrate auth service\n- [ ] Update runbooks\n- [ ] Notify support",
    },
    {
        "page_id": "CONF-102",
        "title": "Incident retro: API latency",
        "space": "ENG",
        "url": "https://demo.atlassian.net/wiki/spaces/ENG/pages/102",
        "labels": ["retro", "incident"],
        "body_excerpt": "Action: add circuit breaker on payments edge.\nAction: write regression tests for retry storm.",
    },
    {
        "page_id": "CONF-201",
        "title": "Product backlog grooming",
        "space": "PROD",
        "url": "https://demo.atlassian.net/wiki/spaces/PROD/pages/201",
        "labels": ["backlog"],
        "body_excerpt": "- [ ] Sync Jira epics\n- [ ] Draft release notes",
    },
]

JIRA_ISSUES = [
    {
        "issue_key": "DEMO-42",
        "project": "DEMO",
        "summary": "Add circuit breaker on payments edge",
        "status": "To Do",
        "issue_type": "Bug",
        "description": "From Confluence retro CONF-102. Implement breaker + metrics.",
    },
    {
        "issue_key": "DEMO-43",
        "project": "DEMO",
        "summary": "Regression tests for retry storm",
        "status": "To Do",
        "issue_type": "Task",
        "description": "Cover exponential backoff and idempotency keys.",
    },
    {
        "issue_key": "DEMO-44",
        "project": "DEMO",
        "summary": "Migrate auth service to OIDC",
        "status": "In Progress",
        "issue_type": "Story",
        "description": "From platform checklist CONF-101.",
    },
]

TASKS_STORE: list[dict] = []
JIRA_CREATED: list[dict] = []
GITHUB_ACTIVITY: list[dict] = []

GITHUB_COMMITS = [
    {
        "repo": "demo-org/demo-app",
        "sha": "a1b2c3d4e5f6789012345678901234567890abcd",
        "commit_sha": "a1b2c3d4e5f6",
        "author": "alice.dev",
        "author_name": "Alice Developer",
        "message": "feat: add circuit breaker metrics dashboard",
        "date": "2024-06-01T14:22:00Z",
        "url": "https://github.com/demo-org/demo-app/commit/a1b2c3d4e5f6",
    },
    {
        "repo": "demo-org/demo-app",
        "sha": "b2c3d4e5f6789012345678901234567890abcde1",
        "commit_sha": "b2c3d4e5f678",
        "author": "bob.ops",
        "author_name": "Bob Ops",
        "message": "fix: tighten retry storm regression tests",
        "date": "2024-06-01T11:05:00Z",
        "url": "https://github.com/demo-org/demo-app/commit/b2c3d4e5f678",
    },
    {
        "repo": "demo-org/demo-app",
        "sha": "c3d4e5f6789012345678901234567890abcde123",
        "commit_sha": "c3d4e5f67890",
        "author": "carol.platform",
        "author_name": "Carol Platform",
        "message": "docs: update MCP bridge runbook for Studio demos",
        "date": "2024-05-31T18:40:00Z",
        "url": "https://github.com/demo-org/demo-app/commit/c3d4e5f67890",
    },
]
