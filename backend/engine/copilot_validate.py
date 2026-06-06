"""
Validation profile for orchestrator / Copilot workflows.

Studio palette workflows use orchestrator-backend rules via
:func:`copilot.orchestrator_validator.validate_workflow`, then a
Studio-approved type gate.
"""
from __future__ import annotations

from copilot.orchestrator_validator import validate_workflow as validate_orchestrator

import os

from llm import gemini_configured

from .integration_env import require_atlassian, require_github_token, resolve_github_repo
from .mcp_nodes import is_mcp_node_type

from .studio_nodes import STUDIO_APPROVED_NODE_TYPES
from .validation_codes import ValidationErrorCode
from .validator import ValidationResult


def uses_orchestrator_profile(dag: dict) -> bool:
    return True


def validate_dag_for_api(dag: dict) -> ValidationResult:
    """Single entry for /validate, /run preflight, and UI validate button."""
    err = validate_orchestrator(dag)
    if err:
        result = ValidationResult()
        result.add(
            ValidationErrorCode.ORPHAN_NODE
            if "no incoming edge" in err
            else ValidationErrorCode.MISSING_REQUIRED_PARAM
            if "missing required config" in err
            else ValidationErrorCode.UNKNOWN_TYPE
            if "unknown type" in err
            else ValidationErrorCode.BAD_EDGE,
            err,
            field="edges.sourceHandle" if "sourceHandle" in err else None,
        )
        return result

    result = ValidationResult()
    for n in dag.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        ntype = n.get("type")
        if ntype and ntype not in STUDIO_APPROVED_NODE_TYPES:
            result.add(
                ValidationErrorCode.UNKNOWN_TYPE,
                f"Node {n.get('id')!r}: type {ntype!r} is not a Studio-approved node.",
            )
    if not result.valid:
        return result
    result = _validate_integration_env(dag, result)
    if not result.valid:
        return result
    return result


def _validate_integration_env(dag: dict, result: ValidationResult) -> ValidationResult:
    nodes = [n for n in (dag.get("nodes") or []) if isinstance(n, dict)]
    for n in nodes:
        ntype = n.get("type")
        cfg = n.get("config") or {}
        nid = n.get("id") or ntype
        try:
            if ntype == "agent" and not gemini_configured():
                result.add(
                    ValidationErrorCode.MISSING_REQUIRED_PARAM,
                    "AI Agent nodes require GEMINI_API_KEY in backend/.env.",
                )
            elif ntype == "github":
                require_github_token()
                action = cfg.get("action") or "list-repos"
                if action != "list-repos":
                    resolve_github_repo(cfg.get("repo"))
            elif ntype == "teams":
                from .integration_env import require_teams_webhook
                require_teams_webhook(cfg.get("webhookUrl"))
            elif ntype == "slack":
                from .integration_env import require_slack_auth
                require_slack_auth(cfg_webhook=cfg.get("webhookUrl"))
            elif ntype == "telegram":
                from .integration_env import require_telegram
                require_telegram(cfg_token=cfg.get("botToken"), cfg_chat_id=cfg.get("chatId"))
            elif ntype == "gmail":
                from .integration_env import require_gmail
                require_gmail()
            elif ntype == "notion":
                from .integration_env import require_notion
                require_notion()
            elif ntype == "outlook":
                from .integration_env import require_outlook
                require_outlook(cfg_tenant=cfg.get("tenantId"))
            elif is_mcp_node_type(ntype):
                _validate_mcp_env(ntype, cfg, result, nid)
        except ValueError as exc:
            result.add(
                ValidationErrorCode.MISSING_REQUIRED_PARAM,
                f"Node {nid!r}: {exc}",
            )
    return result


def _validate_mcp_env(ntype: str, cfg: dict, result: ValidationResult, nid: str) -> None:
    from .mcp_nodes import mcp_integration_for_node_type

    integration = mcp_integration_for_node_type(ntype)
    if ntype == "mcp":
        raw_integration = str(cfg.get("integration") or "atlassian").strip().lower()
        integration = (
            "atlassian"
            if raw_integration in ("jira", "confluence", "atlassian", "studio_bridge")
            else "github"
        )
    if integration == "atlassian":
        site_url = (
            cfg.get("jiraSiteUrl")
            or cfg.get("confluenceSiteUrl")
            or cfg.get("atlassianSiteUrl")
            or os.getenv("ATLASSIAN_SITE_URL")
        )
        email = (
            cfg.get("jiraEmail")
            or cfg.get("confluenceEmail")
            or cfg.get("atlassianEmail")
            or os.getenv("ATLASSIAN_EMAIL")
        )
        api_token = (
            cfg.get("jiraApiToken")
            or cfg.get("confluenceApiToken")
            or cfg.get("atlassianApiToken")
            or os.getenv("ATLASSIAN_API_TOKEN")
        )
        if not site_url:
            raise ValueError("Atlassian URL is required (set in UI or ATLASSIAN_SITE_URL in .env)")
        if not email:
            raise ValueError("Atlassian email is required (set in UI or ATLASSIAN_EMAIL in .env)")
        if not api_token:
            raise ValueError("Atlassian API token is required (set in UI or ATLASSIAN_API_TOKEN in .env)")
    elif integration == "github":
        token = (
            cfg.get("githubToken")
            or os.getenv("GITHUB_TOKEN")
            or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        )
        repo = cfg.get("githubRepo") or os.getenv("GITHUB_REPO")
        if not token:
            raise ValueError("GitHub Token is required (set in UI or GITHUB_TOKEN in .env)")
        resolve_github_repo(repo)
