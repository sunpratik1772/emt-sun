"""Confluence MCP tool handlers."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integrations.mcp.confluence.connectivity import ConfluenceClient
from integrations.mcp.credentials import resolve_atlassian

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _BACKEND_ROOT.parent


def markdown_to_storage_html(md: str) -> str:
    parts: list[str] = []
    in_list = False
    for line in md.splitlines():
        if line.startswith("### "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip().startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{html.escape(line.strip()[2:])}</li>")
        elif line.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<p>{html.escape(line.strip())}</p>")
    if in_list:
        parts.append("</ul>")
    return "\n".join(parts) or "<p>Architecture overview</p>"


def _analyze_studio_repo(repo_root: Path) -> str:
    lines = [
        "# Sheep Studio — Architecture Overview",
        "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by Studio MCP workflow.*",
        "",
        "## Purpose",
        "Sheep Studio is a workflow builder and execution engine for data pipelines, "
        "AI agents, and integrations (including MCP tools for Confluence, Jira, and GitHub).",
        "",
        "## High-level components",
    ]
    components = [
        ("frontend/", "React Studio UI — canvas, node inspector, run/stream UX"),
        ("backend/app/", "FastAPI HTTP API — /run, /validate, /copilot, /node-manifest"),
        ("backend/engine/", "DAG runner, node registry, orchestrator-style handlers"),
        ("backend/generation/", "Agent harness — workflow generation and validation"),
        ("backend/integrations/mcp/", "MCP bridge for Atlassian + GitHub tool calls"),
        ("backend/connectors/", "Declarative data connectors (CSV, SQLite, Solr, Oracle)"),
    ]
    for path, desc in components:
        full = repo_root / path.rstrip("/")
        exists = "✓" if full.exists() else "—"
        lines.append(f"- **{path}** ({exists}) — {desc}")

    nodes_dir = repo_root / "backend" / "engine" / "nodes"
    if nodes_dir.is_dir():
        lines.extend(["", "## Registered node types (sample)", ""])
        for yaml_path in sorted(nodes_dir.glob("*.yaml"))[:20]:
            lines.append(f"- `{yaml_path.stem}`")
        if len(list(nodes_dir.glob("*.yaml"))) > 20:
            lines.append(f"- … and {len(list(nodes_dir.glob('*.yaml'))) - 20} more node types")

    readme = repo_root / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8", errors="replace")[:800]
        lines.extend(["", "## Repository notes (excerpt)", "", text])

    return "\n".join(lines)


def _page_row(page: dict[str, Any], atl: dict[str, str], title: str) -> dict[str, Any]:
    page_id = str(page.get("id", ""))
    links = page.get("_links") or {}
    webui = links.get("webui") or links.get("base") or ""
    page_url = f"{atl['site_url']}/wiki{webui}" if webui.startswith("/") else webui
    return {
        "page_id": page_id,
        "title": page.get("title", title),
        "space": atl["confluence_space"],
        "url": page_url,
        "mode": "live",
    }


def confluence_publish_report(params: dict[str, Any]) -> dict[str, Any]:
    """Publish an AI-generated markdown report to Confluence."""
    atl = resolve_atlassian(params)
    client = ConfluenceClient(atl["site_url"], atl["email"], atl["api_token"])
    upstream = params.get("data") or []
    if not isinstance(upstream, list):
        upstream = []
    first = upstream[0] if upstream and isinstance(upstream[0], dict) else {}
    base_title = params.get("title") or first.get("title") or "Studio workflow analysis"
    title = base_title
    if not params.get("fixed_title"):
        title = f"{base_title} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')})"
    body_md = (
        params.get("body_markdown")
        or params.get("body")
        or first.get("body_markdown")
        or first.get("body")
        or ""
    )
    if not body_md.strip():
        metrics = first.get("metrics_preview") or upstream
        body_md = (
            "# Workflow analysis\n\n"
            "_No body_markdown supplied; showing metrics table._\n\n"
            + "\n".join(
                f"- {r}" if isinstance(r, str) else f"- `{r}`"
                for r in (metrics[:20] if isinstance(metrics, list) else [metrics])
            )
        )
    page = client.create_page(
        atl["confluence_space"],
        title,
        markdown_to_storage_html(body_md),
    )
    return {"rows": [_page_row(page, atl, title)], "rowCount": 1, "mode": "live"}


def studio_publish_architecture_doc(params: dict[str, Any]) -> dict[str, Any]:
    atl = resolve_atlassian(params)
    client = ConfluenceClient(atl["site_url"], atl["email"], atl["api_token"])
    repo = Path(params.get("repo_root") or str(_REPO_ROOT))
    if params.get("analyze_repo") == "dbsherpa-studio":
        repo = Path(params.get("dbsherpa_studio_path") or _REPO_ROOT)
    base_title = params.get("title") or "Sheep Studio — Architecture"
    title = base_title
    if not params.get("fixed_title"):
        title = f"{base_title} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')})"
    md = _analyze_studio_repo(repo)
    page = client.create_page(
        atl["confluence_space"],
        title,
        markdown_to_storage_html(md),
    )
    return {"rows": [_page_row(page, atl, title)], "rowCount": 1, "mode": "live"}


CONFLUENCE_TOOLS = {
    "confluence_publish_report": confluence_publish_report,
    "studio_publish_architecture_doc": studio_publish_architecture_doc,
}
