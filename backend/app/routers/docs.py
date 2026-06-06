"""
Documentation endpoints – serve markdown guides from docs/
"""
from __future__ import annotations
import re
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional

router = APIRouter(prefix="/docs", tags=["docs"])

DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"

_DOC_GUIDES = [
    ("engineering-onboarding", "Engineering Onboarding", "engineering-onboarding.md"),
    ("backend-structure",      "Backend Structure",      "backend-structure.md"),
    ("architecture",           "Architecture",           "architecture.md"),
    ("architecture-principles","Design Principles",      "architecture-principles.md"),
    ("frontend-architecture",  "Frontend Architecture",  "frontend-architecture.md"),
    ("node-catalogue",         "Node Catalogue",         "node-catalogue.md"),
    ("creating-nodes",         "Creating Nodes",         "creating-nodes.md"),
    ("data-source-onboarding", "Data Source Onboarding",  "data-source-onboarding.md"),
    ("generation-harness",     "Sherpa Agent Harness",   "generation-harness.md"),
    ("mcp-integrations",       "MCP Integrations",       "mcp-integrations.md"),
    ("database",               "Database",               "database.md"),
]

# Brief descriptions shown on the overview cards
_DOC_DESCRIPTIONS: dict[str, str] = {
    "engineering-onboarding": "Clone, run, and navigate the repo — `connectors/`, `generation/`, `good_examples/`.",
    "backend-structure":      "Canonical backend layout — packages, imports, and where demos live.",
    "architecture":           "Frontend ↔ FastAPI ↔ DAG runner ↔ generation harness ↔ MCP.",
    "architecture-principles":"GRASP, DRY, KISS, SOLID, YAGNI — how the May 2026 restructure maps to each.",
    "frontend-architecture":  "React module map, Zustand slices, TanStack Query, and Studio shell layout.",
    "node-catalogue":         "All 36 Studio nodes — ports, params, palette sections (YAML + handler pairs).",
    "creating-nodes":         "Add a node: `engine/nodes/<type>.yaml` + `.py`, then `gen_artifacts.py`.",
    "data-source-onboarding": "Register datasets in `connectors/metadata/` for Copilot and extract nodes.",
    "generation-harness":     "Full Sherpa stack — routing, clarification, follow-ups, UI stream, and AgentRunner.",
    "mcp-integrations":       "GitHub/Jira/Confluence MCP credentials, bridge tools, demo vs live, Teams & Outlook status.",
    "database":               "SQLite/MySQL schema — auth, chats, automations, run history.",
}


def _load_md(path: Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    # Strip leading "# Title" line so the frontend can render its own title
    text = re.sub(r"^#\s+[^\n]+\n*", "", text, count=1)
    # Strip leading blockquote description (already shown on overview)
    text = re.sub(r"^(>\s*[^\n]+\n)+\n*", "", text.lstrip())
    # Strip leading --- separator
    text = re.sub(r"^---\s*\n+", "", text.lstrip())
    return text.strip()


@router.get("")
async def get_docs():
    guide_items = []
    for doc_id, title, filename in _DOC_GUIDES:
        content = _load_md(DOCS_DIR / filename)
        if content:
            guide_items.append({
                "id": doc_id,
                "title": title,
                "content": content,
                "description": _DOC_DESCRIPTIONS.get(doc_id, ""),
            })

    payload = {
        "sections": [
            {
                "id": "guides",
                "title": "Guides & Reference",
                "icon": "book-open",
                "items": guide_items,
            },
        ]
    }
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store"},
    )
