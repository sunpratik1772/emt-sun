"""
Workflow CRUD — user workloads stored in the database only.

  workflows table — explicitly saved workflows
  drafts table    — in-flight or Copilot-generated scratch workflows

Vetted Studio demos for agent few-shot live under backend/good_examples/
(read-only; not listed here).

YAML helpers remain for import/export; persisted rows store JSON in workflow_data.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engine.workflow_format import workflow_from_yaml, workflow_to_yaml

from ..auth_deps import feature_guard, require_user_id
from ..database_scope import cast_workflow_vote
from ..schemas import WorkflowYamlParseRequest, WorkflowYamlRenderRequest
from .library import append_audit_log
from ..database import (
    save_workflow_db,
    get_workflow_db,
    delete_workflow_db,
    list_workflows_db,
    save_draft_db,
    get_draft_db,
    delete_draft_db,
    list_drafts_db,
)


_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")
_WORKFLOW_SUFFIXES = {".json", ".yaml", ".yml"}


def _validate_filename(filename: str) -> None:
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail=f"Invalid filename '{filename}'")
    if not any(filename.endswith(s) for s in _WORKFLOW_SUFFIXES):
        raise HTTPException(status_code=400, detail="Workflow filename must end with .json, .yaml, or .yml")


def _parse_updated_ms(updated_at: str | datetime | None) -> int:
    if not updated_at:
        return 0
    try:
        if isinstance(updated_at, datetime):
            return int(updated_at.timestamp() * 1000)
        iso_str = str(updated_at).replace("Z", "+00:00")
        return int(datetime.fromisoformat(iso_str).timestamp() * 1000)
    except Exception:
        return 0


def _dag_from_row(row: dict) -> dict:
    raw = row.get("workflow_data")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}


def _row_to_list_item(row: dict) -> dict:
    dag = _dag_from_row(row)
    return {
        "filename": row.get("filename"),
        "workflow_id": row.get("workflow_id") or dag.get("workflow_id"),
        "name": row.get("name") or dag.get("name") or row.get("filename"),
        "description": row.get("description") or dag.get("description"),
        "node_count": len(dag.get("nodes") or []),
        "modified_ms": _parse_updated_ms(row.get("updated_at")),
        "upvote_count": int(row.get("upvote_count") or 0),
        "downvote_count": int(row.get("downvote_count") or 0),
    }


def _normalize_display_name(name: str) -> str:
    return (name or "").strip().casefold()


def _find_workflows_with_display_name(
    display_name: str,
    user_id: str,
    *,
    exclude_filename: str | None = None,
) -> list[dict]:
    """Other saved workflows that share the same display name (case-insensitive)."""
    needle = _normalize_display_name(display_name)
    if not needle:
        return []
    conflicts: list[dict] = []
    for row in list_workflows_db(user_id):
        fname = str(row.get("filename") or "")
        if not fname or fname == exclude_filename:
            continue
        dag = _dag_from_row(row)
        row_name = _normalize_display_name(
            str(row.get("name") or dag.get("name") or ""),
        )
        if row_name == needle:
            conflicts.append(_row_to_list_item(row))
    return conflicts


def _save_workflow_row(filename: str, dag: dict[str, Any], user_id: str) -> dict:
    _validate_filename(filename)
    save_workflow_db(
        filename=filename,
        workflow_id=dag.get("workflow_id"),
        name=dag.get("name"),
        description=dag.get("description"),
        workflow_data=json.dumps(dag),
        user_id=user_id,
    )
    return {"saved": filename, "location": "workflows"}


def _save_draft_row(filename: str, dag: dict[str, Any], user_id: str) -> dict:
    _validate_filename(filename)
    save_draft_db(
        filename=filename,
        workflow_id=dag.get("workflow_id"),
        name=dag.get("name"),
        description=dag.get("description"),
        workflow_data=json.dumps(dag),
        user_id=user_id,
    )
    return {"saved": filename, "location": "drafts"}


router = APIRouter(tags=["workflows"])


@router.post("/workflow-format/yaml-to-json")
def parse_workflow_yaml(req: WorkflowYamlParseRequest) -> dict:
    """Convert human-authored workflow YAML into the runtime JSON DAG."""
    try:
        return {"workflow": workflow_from_yaml(req.content)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/workflow-format/json-to-yaml")
def render_workflow_yaml(req: WorkflowYamlRenderRequest) -> dict:
    """Convert the runtime JSON DAG into downloadable workflow YAML."""
    return {"content": workflow_to_yaml(req.workflow)}


@router.get("/workflows/catalog")
def workflow_catalog(user_id: str = Depends(feature_guard("workflows"))) -> dict:
    """Canonical saved + draft workflows — one display name per row (newest wins duplicates)."""
    from ..workflow_library import build_workflow_catalog

    return {"entries": [e.to_dict() for e in build_workflow_catalog(user_id)]}


@router.get("/workflows/resolve")
def resolve_workflow_by_name(
    name: str = Query(..., alias="name"),
    user_id: str = Depends(feature_guard("workflows")),
) -> dict:
    """Resolve a display name to the canonical catalog entry and workflow JSON."""
    from ..workflow_library import resolve_workflow_by_display_name

    query = (name or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter 'name' is required")
    return resolve_workflow_by_display_name(query, user_id)


@router.get("/workflows/search")
def search_workflows_endpoint(
    q: str,
    limit: int = 3,
    user_id: str = Depends(feature_guard("workflows")),
) -> dict:
    """Resolve a workflow by natural-language name — load, disambiguate (≤3), or not_found."""
    from ..workflow_library import resolve_workflow_by_display_name

    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if limit <= 1:
        resolved = resolve_workflow_by_display_name(query, user_id)
        if resolved.get("action") == "load":
            return {
                "action": "load",
                "query": query,
                "canonical_name": resolved.get("canonical_name"),
                "match": {
                    "filename": resolved.get("filename"),
                    "name": resolved.get("canonical_name"),
                },
                "workflow": resolved.get("workflow"),
            }
        return {"action": "not_found", "query": query, "matches": []}

    from ..workflow_search import search_workflows
    from ..database import list_workflow_library_rows
    from ..workflow_library import catalog_entry_for_filename, load_workflow_for_catalog_entry

    rows = list_workflow_library_rows(user_id)
    raw = search_workflows(rows, query, limit=limit)
    if raw.get("action") == "load" and isinstance(raw.get("workflow"), dict):
        match = raw.get("match") or {}
        entry = catalog_entry_for_filename(str(match.get("filename") or ""), user_id)
        if entry:
            wf = load_workflow_for_catalog_entry(entry, user_id) or raw["workflow"]
            return {
                **raw,
                "canonical_name": entry.canonical_name,
                "match": {**match, "name": entry.canonical_name},
                "workflow": wf,
            }
    if raw.get("action") == "disambiguate":
        matches = []
        for m in raw.get("matches") or []:
            if not isinstance(m, dict):
                continue
            entry = catalog_entry_for_filename(str(m.get("filename") or ""), user_id)
            if entry:
                matches.append({**m, "name": entry.canonical_name})
            else:
                matches.append(m)
        return {**raw, "matches": matches}
    return raw


@router.get("/workflows")
def list_workflows(user_id: str = Depends(feature_guard("workflows"))) -> dict:
    """List saved workflows from the database."""
    try:
        rows = list_workflows_db(user_id)
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).error(f"Failed to list workflows from DB: {exc}")
        rows = []
    workflows = [_row_to_list_item(row) for row in rows]
    workflows.sort(key=lambda r: r.get("modified_ms") or 0, reverse=True)
    return {"workflows": workflows}


@router.get("/workflows/{filename}")
def get_workflow(filename: str, user_id: str = Depends(feature_guard("workflows"))) -> dict:
    _validate_filename(filename)
    row = get_workflow_db(filename, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in workflows")
    dag = _dag_from_row(row)
    if not dag:
        raise HTTPException(status_code=404, detail=f"'{filename}' has no workflow data")
    return dag


class WorkflowVoteBody(BaseModel):
    vote: str = Field(..., description="up or down")
    promote_to_folder: bool | None = Field(default=None, description="Override good-example folder promotion")
    promote_to_table: bool | None = Field(default=None, description="Override good-example table promotion")


@router.post("/workflows/{filename}/vote")
def vote_workflow(
    filename: str,
    body: WorkflowVoteBody,
    user_id: str = Depends(feature_guard("workflows")),
) -> dict:
    _validate_filename(filename)
    try:
        result = cast_workflow_vote(
            user_id,
            user_id,
            filename,
            body.vote,
            promote_to_folder=body.promote_to_folder,
            promote_to_table=body.promote_to_table,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/workflows/{filename}")
def save_workflow(
    filename: str,
    dag: dict[str, Any],
    replace: bool = Query(False, description="Replace other saved workflows that share this display name"),
    user_id: str = Depends(feature_guard("workflows")),
) -> dict:
    display_name = str(dag.get("name") or "").strip()
    conflicts = _find_workflows_with_display_name(display_name, user_id, exclude_filename=filename)
    if conflicts and not replace:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "workflow_name_conflict",
                "message": f"A saved workflow named '{display_name}' already exists.",
                "name": display_name,
                "conflicts": conflicts,
            },
        )
    if conflicts and replace:
        for row in conflicts:
            delete_workflow_db(str(row["filename"]), user_id)

    res = _save_workflow_row(filename, dag, user_id)
    append_audit_log({
        "actor": "user",
        "action": "workflow.save",
        "resource": filename,
        "detail": dag.get("name") or filename,
    })
    return res


@router.delete("/workflows/{filename}")
def delete_workflow(filename: str, user_id: str = Depends(feature_guard("workflows"))) -> dict:
    _validate_filename(filename)
    if not get_workflow_db(filename, user_id):
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in workflows")
    delete_workflow_db(filename, user_id)
    append_audit_log({
        "actor": "user",
        "action": "workflow.delete",
        "resource": filename,
    })
    return {"deleted": filename, "location": "workflows"}


drafts_router = APIRouter(tags=["drafts"])


@drafts_router.get("/drafts")
def list_drafts(user_id: str = Depends(feature_guard("workflows"))) -> dict:
    try:
        rows = list_drafts_db(user_id)
    except Exception as exc:
        from logging import getLogger
        getLogger(__name__).error(f"Failed to list drafts from DB: {exc}")
        rows = []
    drafts = [_row_to_list_item(row) for row in rows]
    drafts.sort(key=lambda r: r.get("modified_ms") or 0, reverse=True)
    return {"drafts": drafts}


@drafts_router.get("/drafts/{filename}")
def get_draft(filename: str, user_id: str = Depends(feature_guard("workflows"))) -> dict:
    _validate_filename(filename)
    row = get_draft_db(filename, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in drafts")
    dag = _dag_from_row(row)
    if not dag:
        raise HTTPException(status_code=404, detail=f"'{filename}' has no draft data")
    return dag


@drafts_router.post("/drafts/{filename}")
def save_draft(filename: str, dag: dict[str, Any], user_id: str = Depends(feature_guard("workflows"))) -> dict:
    return _save_draft_row(filename, dag, user_id)


@drafts_router.delete("/drafts/{filename}")
def delete_draft(filename: str, user_id: str = Depends(feature_guard("workflows"))) -> dict:
    _validate_filename(filename)
    if not get_draft_db(filename, user_id):
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in drafts")
    delete_draft_db(filename, user_id)
    append_audit_log({
        "actor": "user",
        "action": "draft.delete",
        "resource": filename,
    })
    return {"deleted": filename, "location": "drafts"}


@drafts_router.post("/drafts/{filename}/promote")
def promote_draft(
    filename: str,
    body: dict[str, Any],
    user_id: str = Depends(feature_guard("workflows")),
) -> dict:
    """Promote a draft to a saved workflow (DB → DB)."""
    target = body.get("target_filename")
    if not target:
        raise HTTPException(status_code=400, detail="target_filename is required")

    _validate_filename(filename)
    _validate_filename(target)

    row = get_draft_db(filename, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in drafts")

    dag = _dag_from_row(row)
    if body.get("name"):
        dag["name"] = body["name"]

    display_name = str(dag.get("name") or "").strip()
    replace = bool(body.get("replace"))
    conflicts = _find_workflows_with_display_name(display_name, user_id, exclude_filename=target)
    if conflicts and not replace:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "workflow_name_conflict",
                "message": f"A saved workflow named '{display_name}' already exists.",
                "name": display_name,
                "conflicts": conflicts,
            },
        )
    if conflicts and replace:
        for row in conflicts:
            delete_workflow_db(str(row["filename"]), user_id)

    _save_workflow_row(target, dag, user_id)
    delete_draft_db(filename, user_id)
    return {"promoted": filename, "saved_as": target, "location": "workflows"}
