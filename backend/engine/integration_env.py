"""Mandatory integration credentials — integration nodes fail fast when env is missing."""
from __future__ import annotations

import os

_PLACEHOLDER_REPOS = frozenset({
    "your-github-repo-name",
    "owner/repo",
    "owner/name",
    "your-org/your-repo",
})


def require_env(name: str, *, hint: str = "") -> str:
    val = (os.getenv(name) or "").strip()
    if not val:
        msg = f"{name} is required in backend/.env"
        if hint:
            msg += f" ({hint})"
        raise ValueError(msg)
    return val


def require_any_env(*names: str, hint: str = "") -> str:
    for name in names:
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    joined = " or ".join(names)
    msg = f"One of {joined} is required in backend/.env"
    if hint:
        msg += f" ({hint})"
    raise ValueError(msg)


def resolve_github_repo(cfg_repo: str | None = None) -> str:
    raw = (cfg_repo or "").strip()
    
    # Extract owner/repo from URL if it's a URL
    if "github.com/" in raw:
        parts = raw.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            raw = f"{parts[0]}/{parts[1]}"
            
    if raw.endswith(".git"):
        raw = raw[:-4]
            
    # Helper to check if a repo string is a placeholder or invalid
    def is_placeholder_or_invalid(s: str) -> bool:
        s = s.lower().strip()
        if not s or "/" not in s:
            return True
        parts = s.split("/")
        if len(parts) != 2:
            return True
        owner, name = parts[0], parts[1]
        exact_placeholders = {
            "your-github-repo-name",
            "owner/repo",
            "owner/name",
            "your-org/your-repo",
            "owner/repository",
            "user/repo",
            "username/repo",
        }
        if s in exact_placeholders:
            return True
        if owner.startswith("your-") or name.startswith("your-"):
            return True
        placeholder_owners = {"owner", "your-org", "your-username", "username", "dummy", "placeholder"}
        placeholder_names = {"your-repo", "your-github-repo-name", "dummy", "placeholder"}
        if owner in placeholder_owners or name in placeholder_names:
            return True
        return False

    if is_placeholder_or_invalid(raw):
        env_repo = (os.getenv("GITHUB_REPO") or "").strip()
        if env_repo:
            raw = env_repo
            
    if is_placeholder_or_invalid(raw):
        raise ValueError(
            "GitHub repo is required: set config.repo to owner/name or GITHUB_REPO in backend/.env"
        )
    return raw


def require_github_token() -> str:
    return require_any_env("GITHUB_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN")


def require_atlassian() -> dict[str, str]:
    return {
        "site_url": require_env("ATLASSIAN_SITE_URL").rstrip("/"),
        "email": require_env("ATLASSIAN_EMAIL"),
        "api_token": require_env("ATLASSIAN_API_TOKEN"),
        "confluence_space": (os.getenv("CONFLUENCE_SPACE_KEY") or "").strip() or "MFS",
        "jira_project": (os.getenv("JIRA_PROJECT_KEY") or "").strip() or "DEMO",
    }


def require_teams_webhook(cfg_webhook: str | None = None) -> str:
    webhook = (cfg_webhook or os.getenv("TEAMS_INCOMING_WEBHOOK_URL") or "").strip()
    if not webhook:
        raise ValueError(
            "TEAMS_INCOMING_WEBHOOK_URL is required in backend/.env (or pass webhookUrl in node config)"
        )
    return webhook


def require_slack_auth(*, cfg_webhook: str | None = None) -> tuple[str, str]:
    token = (os.getenv("SLACK_API_TOKEN_NOW") or os.getenv("SLACK_BOT_TOKEN") or "").strip()
    if token:
        return "bot_token", token
    webhook = (cfg_webhook or os.getenv("SLACK_WEBHOOK_URL") or "").strip()
    if webhook:
        return "webhook", webhook
    raise ValueError(
        "SLACK_BOT_TOKEN (or SLACK_API_TOKEN_NOW) or SLACK_WEBHOOK_URL is required in backend/.env"
    )


def require_telegram(*, cfg_token: str | None = None, cfg_chat_id: str | None = None) -> tuple[str, str]:
    token = (cfg_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (cfg_chat_id or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required in backend/.env (or pass botToken in node config)")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID is required in backend/.env (or pass chatId in node config)")
    return token, chat_id


def require_gmail() -> None:
    require_env("GMAIL_CLIENT_SECRET")


def require_notion() -> str:
    return require_env("NOTION_API_KEY")


def require_outlook(*, cfg_tenant: str | None = None) -> dict[str, str]:
    tenant = (cfg_tenant or os.getenv("OUTLOOK_TENANT_ID") or "").strip()
    client_id = (os.getenv("OUTLOOK_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("OUTLOOK_CLIENT_SECRET") or "").strip()
    missing = [
        name
        for name, val in (
            ("OUTLOOK_TENANT_ID", tenant),
            ("OUTLOOK_CLIENT_ID", client_id),
            ("OUTLOOK_CLIENT_SECRET", client_secret),
        )
        if not val
    ]
    if missing:
        raise ValueError(
            f"{', '.join(missing)} required in backend/.env to send via Outlook Graph"
        )
    return {"tenant_id": tenant, "client_id": client_id, "client_secret": client_secret}
