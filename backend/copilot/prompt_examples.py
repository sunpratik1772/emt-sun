"""
Dynamic example prompt generator for the Copilot panel.

Generates interesting, demo-worthy prompts from the live registry:
  - Data sources (YAML metadata)
  - Node types (from engine.registry)
  - Integrations (MCP, GitHub, Outlook, Teams)
  - Skills (surveillance scenarios)

Every prompt uses real dataset names, column names, and node types
so they work out of the box when clicked.
"""
from __future__ import annotations

import json
import re
from typing import Any

from engine.mcp_nodes import active_mcp_tools


ALLOWED_TAGS = {
    "advanced",
    "ai",
    "csv",
    "data",
    "email",
    "excel",
    "github",
    "integrations",
    "logic",
    "mcp",
    "nodes",
    "outlook",
    "pipeline",
    "surveillance",
    "teams",
}


def generate_example_prompts() -> dict[str, list[dict]]:
    """Return AI-generated build + ask prompts grounded in live registry data."""
    sources = _load_sources()
    integrations = _load_integrations()
    skills = _load_skills()
    node_groups = _load_node_groups()

    ai_prompts = _generate_with_gemini(sources, integrations, skills, node_groups)
    if ai_prompts:
        return ai_prompts
    return _fallback_prompts(sources, integrations, skills)


def _generate_with_gemini(
    sources: list[dict],
    integrations: list[dict],
    skills: list[dict],
    node_groups: dict[str, list[str]],
) -> dict[str, list[dict]] | None:
    try:
        from llm import gemini_configured, get_default_adapter

        if not gemini_configured():
            return None

        system_prompt = (
            "You generate clickable example prompts for dbSherpa Studio's Copilot drawer. "
            "Every suggestion must be directly buildable from the provided live manifest. "
            "Prefer dynamic, demo-worthy, slightly off-beat workflows that create concrete artifacts "
            "such as Excel, CSV, Jira, Confluence, GitHub, Outlook, or Teams outputs. "
            "Use exact source IDs, exact column names, and exact node/integration names from the manifest. "
            "For MCP, only mention exact working Studio bridge tools from manifest.mcp_tools; "
            "never invent create_confluence_page. "
            "Return only JSON."
        )
        user_prompt = json.dumps(
            {
                "task": "Generate 6 build prompts and 4 ask prompts.",
                "output_schema": {
                    "build_prompts": [{"text": "string", "tag": "one allowed tag"}],
                    "ask_prompts": [{"text": "string", "tag": "one allowed tag"}],
                },
                "allowed_tags": sorted(ALLOWED_TAGS),
                "rules": [
                    "Build prompts should sound like user instructions, not documentation.",
                    "Build prompts must mention at least one real source ID or real integration/node.",
                    "Include one build prompt tagged excel, one tagged csv, and one tagged github when those integrations or output nodes exist.",
                    "At least two build prompts should use MCP or another external integration when available.",
                    "At least two build prompts should produce Excel or CSV artifacts when those nodes exist.",
                    "Ask prompts should help users discover available nodes, data, skills, and integrations.",
                    "Keep every prompt under 170 characters where possible.",
                    "Never suggest vague placeholders like finish my draft, connect open nodes, or add CSV at the end without naming real sources, files, or node types.",
                ],
                "manifest": _prompt_context(sources, integrations, skills, node_groups),
            },
            indent=2,
        )
        raw = get_default_adapter().chat_turn(
            system_prompt=system_prompt,
            history=[],
            user_turn=user_prompt,
            temperature=0.75,
            json_mode=True,
        )
        return _coerce_prompt_payload(
            raw,
            allowed_terms=_allowed_manifest_terms(sources, integrations, skills, node_groups),
        )
    except Exception:
        return None


def _prompt_context(
    sources: list[dict],
    integrations: list[dict],
    skills: list[dict],
    node_groups: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "sources": [
            {
                "id": s.get("id"),
                "description": s.get("description"),
                "columns": (s.get("columns") or [])[:16],
            }
            for s in sources
            if s.get("id")
        ],
        "nodes_by_group": node_groups,
        "integrations": [
            {
                "type": i.get("type"),
                "description": i.get("description"),
                "params": (i.get("params") or [])[:14],
            }
            for i in integrations
        ],
        "mcp_tools": list(active_mcp_tools()),
        "working_examples": [
            "backend/good_examples/studio_07_join_analyze_confluence.json uses confluence_publish_report",
            "backend/good_examples/studio_10_leads_tier_mcp_publish.json uses confluence_publish_report and jira_create_issue",
            "backend/good_examples/studio_05_web_github_mcp_briefing.json uses confluence_search_pages",
            "backend/good_examples/studio_09_trades_risk_mcp.json uses jira_create_issue",
            "backend/good_examples/studio_12_market_ticks_spread_monitor.json uses db_query + condition + confluence_publish_report",
            "backend/good_examples/studio_13_confluence_actions_issue_pipeline.json uses confluence_search_pages + confluence_extract_action_items + jira_create_issue",
            "backend/good_examples/studio_14_alerts_ticks_join_publish.json uses hs_alerts/market_ticks join + confluence_publish_report + jira_create_issue",
            "backend/good_examples/studio_16_hs_alerts_anomaly_report.json uses hs_alerts filter + evaluator + Starlark summary + condition + confluence_publish_report",
            "backend/good_examples/studio_17_github_activity_briefing.json uses github_mcp github_list_commits + Starlark briefing + confluence_publish_report",
        ],
        "skills": skills,
    }


def _coerce_prompt_payload(
    raw: str,
    *,
    allowed_terms: set[str],
) -> dict[str, list[dict]] | None:
    try:
        payload = json.loads(_extract_json_object(raw))
    except Exception:
        return None

    build = _coerce_prompt_rows(payload.get("build_prompts"), limit=6, allowed_terms=allowed_terms)
    ask = _coerce_prompt_rows(payload.get("ask_prompts"), limit=4, allowed_terms=allowed_terms)
    if len(build) < 4 or len(ask) < 2:
        return None
    return {"build_prompts": build[:6], "ask_prompts": ask[:4]}


def _extract_json_object(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]


def _coerce_prompt_rows(value: Any, *, limit: int, allowed_terms: set[str]) -> list[dict]:
    if not isinstance(value, list):
        return []
    rows: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        tag = str(item.get("tag") or "").strip().lower()
        if not text:
            continue
        if _is_vague_example_prompt(text):
            continue
        if not _backticked_terms_are_known(text, allowed_terms):
            continue
        if tag not in ALLOWED_TAGS:
            tag = "pipeline"
        rows.append({"text": text, "tag": tag})
        if len(rows) >= limit:
            break
    return rows


def _allowed_manifest_terms(
    sources: list[dict],
    integrations: list[dict],
    skills: list[dict],
    node_groups: dict[str, list[str]],
) -> set[str]:
    terms: set[str] = set()
    for source in sources:
        if source.get("id"):
            terms.add(str(source["id"]))
        terms.update(str(c) for c in source.get("columns", []) if c)
    for integration in integrations:
        if integration.get("type"):
            terms.add(str(integration["type"]))
        terms.update(str(p) for p in integration.get("params", []) if p)
    for skill in skills:
        if skill.get("id"):
            terms.add(str(skill["id"]))
        if skill.get("name"):
            terms.add(str(skill["name"]))
    for group, nodes in node_groups.items():
        terms.add(str(group))
        terms.update(str(n) for n in nodes if n)
    return terms


def _backticked_terms_are_known(text: str, allowed_terms: set[str]) -> bool:
    for term in re.findall(r"`([^`]+)`", text):
        if term not in allowed_terms:
            return False
    return True


_VAGUE_SUGGESTION_RE = re.compile(
    r"finish my draft|connect the open nodes|add a csv export at the end|"
    r"wire (up )?(the )?nodes|finish (my |the )?(draft |unfinished )?workflow|"
    r"complete (my |the )?draft",
    re.IGNORECASE,
)


def _is_vague_example_prompt(text: str) -> bool:
    """Drop generic filler that is not grounded in the live manifest."""
    t = (text or "").strip()
    if not t or _VAGUE_SUGGESTION_RE.search(t):
        return True
    quoted = '"' in t
    dataset = bool(re.search(r"\b[a-z][a-z0-9_]*\.(csv|json|xlsx|yaml)\b", t, re.I)) or bool(
        re.search(r"\bhs_[a-z0-9_]+\b", t, re.I)
    )
    integration = bool(
        re.search(r"\b(outlook|github|confluence|teams|jira|excel|mcp)\b", t, re.I)
    )
    artifact = bool(re.search(r"\b(csv|excel|xlsx|report|digest|briefing|surveillance)\b", t, re.I))
    specificity = sum((quoted, dataset, integration, artifact))
    if re.search(r"\b(finish|complete|connect|wire)\b", t, re.I) and re.search(
        r"\b(workflow|draft|nodes)\b", t, re.I
    ):
        if not quoted and specificity < 2:
            return True
    return specificity == 0 and len(t) < 72


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_sources() -> list[dict]:
    try:
        from connectors import get_registry
        raw = get_registry().to_json().get("sources", [])
        out = []
        for s in raw:
            cols = [c.get("name", "") for c in s.get("columns", [])]
            out.append({
                "id": s.get("id") or s.get("source_id") or "",
                "description": s.get("description", ""),
                "columns": cols,
                "sources": s.get("sources", []),
            })
        return out
    except Exception:
        return []


def _load_integrations() -> list[dict]:
    try:
        from engine.registry import NODE_SPECS, all_specs
        from engine.mcp_nodes import active_mcp_node_types

        active = {s.type_id for s in all_specs()}
        integration_types = list(active_mcp_node_types())
        out = []
        for t in integration_types:
            if t not in active:
                continue
            spec = NODE_SPECS.get(t)
            if spec:
                out.append({
                    "type": t,
                    "description": spec.description,
                    "params": [p.name for p in (spec.params or [])],
                })
        return out
    except Exception:
        return []


def _load_skills() -> list[dict]:
    try:
        from pathlib import Path
        skills_dir = Path(__file__).resolve().parents[1] / "skills"
        out = []
        if skills_dir.exists():
            for f in sorted(skills_dir.glob("*.md")):
                stem = f.stem
                if "agentic" in stem:
                    continue
                name = stem.replace("skills-", "").replace("-", " ").title()
                out.append({"id": stem, "name": name})
        return out
    except Exception:
        return []


def _load_node_groups() -> dict[str, list[str]]:
    try:
        from engine.registry import studio_manifest
        m = studio_manifest()
        groups: dict[str, list[str]] = {}
        for n in m["nodes"]:
            g = n.get("palette_group", "general")
            groups.setdefault(g, []).append(n["type_id"])
        return groups
    except Exception:
        return {}


def _fallback_prompts(
    sources: list[dict],
    integrations: list[dict],
    skills: list[dict],
) -> dict[str, list[dict]]:
    """Deterministic fallback when live LLM prompt generation is unavailable."""
    source_ids = [str(s.get("id")) for s in sources if s.get("id")]
    source_a = source_ids[0] if source_ids else "leads.csv"
    source_b = source_ids[1] if len(source_ids) > 1 else "orders.csv"
    has_mcp = any(str(i.get("type", "")).endswith("_mcp") for i in integrations)
    skill_name = (
        str(skills[0].get("name") or skills[0].get("id"))
        if skills
        else "surveillance"
    )

    build: list[dict[str, str]] = [
        {"text": f"Load `{source_a}`, filter high-risk rows, and export a CSV summary.", "tag": "csv"},
        {"text": f"Create an Excel report from `{source_b}` with sorted top contributors.", "tag": "excel"},
        {"text": "Use github_mcp (github_list_commits), summarize with agent, and publish via confluence_mcp.", "tag": "github"},
        {"text": f"Join `{source_a}` with `{source_b}` and produce a ranked output file.", "tag": "pipeline"},
        {"text": "Build a branch workflow that routes pass/fail records into separate exports.", "tag": "logic"},
    ]
    if has_mcp:
        build.append(
            {"text": "Publish a short Confluence report via `confluence_mcp` after processing the dataset.", "tag": "mcp"}
        )
        build.append(
            {"text": "Extract action items and create follow-up Jira tasks using `jira_mcp` tools.", "tag": "integrations"}
        )
    else:
        build.append(
            {"text": f"Use an AI node to summarize `{source_a}` anomalies into markdown text.", "tag": "ai"}
        )
        build.append(
            {"text": "Build a multi-step transform pipeline with filter, map, and grouped totals.", "tag": "advanced"}
        )

    ask: list[dict[str, str]] = [
        {"text": "Which node types are best for filtering and branching workflow data?", "tag": "nodes"},
        {"text": f"What data sources are available, and how should I use `{source_a}`?", "tag": "data"},
        {"text": f"Which prompt pattern should I use for {skill_name} workflows?", "tag": "surveillance"},
        {"text": "How do I decide between CSV, Excel, and MCP publishing outputs?", "tag": "integrations"},
    ]

    return {"build_prompts": build[:6], "ask_prompts": ask[:4]}


