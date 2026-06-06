"""Canonical workflow library — one display name maps to one saved/draft row.

Suggestions, Sherpa routing, and run resolution must all use this module so names
never diverge between the UI chips and the agent harness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LibraryKind = Literal["saved", "draft"]


@dataclass(frozen=True)
class WorkflowCatalogEntry:
    """Authoritative mapping: canonical display name → library file."""

    canonical_name: str
    filename: str
    kind: LibraryKind
    workflow_id: str | None
    updated_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_name": self.canonical_name,
            "filename": self.filename,
            "kind": self.kind,
            "workflow_id": self.workflow_id,
            "updated_ms": self.updated_ms,
        }


def _parse_updated_ms(updated_at: str | Any | None) -> int:
    from datetime import datetime

    if not updated_at:
        return 0
    try:
        if isinstance(updated_at, datetime):
            return int(updated_at.timestamp() * 1000)
        iso_str = str(updated_at).replace("Z", "+00:00")
        return int(datetime.fromisoformat(iso_str).timestamp() * 1000)
    except Exception:
        return 0


def _canonical_name_from_row(row: dict[str, Any]) -> str:
    from app.database import _workflow_row_to_dag

    dag = _workflow_row_to_dag(row) or {}
    raw = str(row.get("name") or dag.get("name") or "").strip()
    if raw:
        return raw
    filename = str(row.get("filename") or "").strip()
    if filename:
        for suffix in (".json", ".yaml", ".yml"):
            if filename.lower().endswith(suffix):
                return filename[: -len(suffix)].strip()
        return filename
    return ""


def _name_key(name: str) -> str:
    return (name or "").strip().casefold()


def build_workflow_catalog(user_id: str) -> list[WorkflowCatalogEntry]:
    """Saved + draft rows deduped by display name (newest row wins per name)."""
    from app.database import list_workflow_library_rows

    best: dict[str, WorkflowCatalogEntry] = {}
    for row in list_workflow_library_rows(user_id):
        canonical = _canonical_name_from_row(row)
        if not canonical:
            continue
        key = _name_key(canonical)
        kind: LibraryKind = "draft" if row.get("_library_kind") == "draft" else "saved"
        entry = WorkflowCatalogEntry(
            canonical_name=canonical,
            filename=str(row.get("filename") or ""),
            kind=kind,
            workflow_id=str(row.get("workflow_id") or "").strip() or None,
            updated_ms=_parse_updated_ms(row.get("updated_at")),
        )
        prev = best.get(key)
        if prev is None or entry.updated_ms >= prev.updated_ms:
            best[key] = entry
    return sorted(best.values(), key=lambda e: (-e.updated_ms, e.canonical_name.lower()))


def catalog_lookup_exact(name: str, user_id: str) -> WorkflowCatalogEntry | None:
    """Case-insensitive exact match on canonical display name."""
    needle = _name_key(name)
    if not needle:
        return None
    for entry in build_workflow_catalog(user_id):
        if _name_key(entry.canonical_name) == needle:
            return entry
    return None


def load_workflow_for_catalog_entry(entry: WorkflowCatalogEntry, user_id: str) -> dict[str, Any] | None:
    from app.database import get_draft_db, get_workflow_db

    row = get_workflow_db(entry.filename, user_id) if entry.kind == "saved" else get_draft_db(entry.filename, user_id)
    if not row:
        return None
    from app.database import _workflow_row_to_dag

    dag = _workflow_row_to_dag(row)
    if not dag:
        return None
    out = dict(dag)
    out["name"] = entry.canonical_name
    return out


def catalog_entry_for_filename(filename: str, user_id: str) -> WorkflowCatalogEntry | None:
    fname = (filename or "").strip()
    if not fname:
        return None
    for entry in build_workflow_catalog(user_id):
        if entry.filename == fname:
            return entry
    return None


def resolve_workflow_by_display_name(name: str, user_id: str) -> dict[str, Any]:
    """Resolve a user-facing name to the canonical catalog entry + workflow JSON.

    Returns:
        action: load | not_found
        canonical_name, filename, kind, workflow (when load)
    """
    query = (name or "").strip()
    if not query:
        return {"action": "not_found", "query": query}

    exact = catalog_lookup_exact(query, user_id)
    if exact:
        workflow = load_workflow_for_catalog_entry(exact, user_id)
        if workflow:
            return {
                "action": "load",
                "query": query,
                "canonical_name": exact.canonical_name,
                "filename": exact.filename,
                "kind": exact.kind,
                "workflow": workflow,
            }

    from app.database import list_workflow_library_rows
    from app.workflow_search import search_workflows

    result = search_workflows(list_workflow_library_rows(user_id), query, limit=1)
    if result.get("action") not in ("load", "disambiguate"):
        return {"action": "not_found", "query": query}

    matches = result.get("matches") or []
    match = result.get("match")
    filename = ""
    if isinstance(match, dict):
        filename = str(match.get("filename") or "")
    elif matches and isinstance(matches[0], dict):
        filename = str(matches[0].get("filename") or "")

    workflow = result.get("workflow") if result.get("action") == "load" else None
    if not workflow and filename:
        entry = catalog_entry_for_filename(filename, user_id)
        if entry:
            workflow = load_workflow_for_catalog_entry(entry, user_id)

    entry = catalog_entry_for_filename(filename, user_id) if filename else None
    if entry and workflow:
        workflow = dict(workflow)
        workflow["name"] = entry.canonical_name
        return {
            "action": "load",
            "query": query,
            "canonical_name": entry.canonical_name,
            "filename": entry.filename,
            "kind": entry.kind,
            "workflow": workflow,
        }

    return {"action": "not_found", "query": query}


def workflow_exists_in_catalog(name: str, user_id: str) -> bool:
    """True when the name resolves to a catalog entry (exact or scored search)."""
    return resolve_workflow_by_display_name(name, user_id).get("action") == "load"


def get_workflow_by_canonical_name(name: str, user_id: str) -> dict[str, Any] | None:
    """Load workflow JSON by display name — always uses catalog canonical name."""
    resolved = resolve_workflow_by_display_name(name, user_id)
    if resolved.get("action") != "load":
        return None
    wf = resolved.get("workflow")
    return wf if isinstance(wf, dict) else None
