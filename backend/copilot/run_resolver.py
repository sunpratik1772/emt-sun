"""Resolve workflow + run_log from SherpaRoute metadata."""
from __future__ import annotations

import json
from typing import Any

from app.database import get_run_log_db, get_workflow_by_name_db, list_db_run_logs
from app.request_context import get_current_user_id


def resolve_run_context(
    route_metadata: dict[str, Any],
    *,
    canvas_workflow: dict[str, Any] | None = None,
    canvas_run_log: list[dict[str, Any]] | None = None,
    canvas_run_result: dict[str, Any] | None = None,
    canvas_run_error: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, str | None]:
    """
    Return (workflow, run_log, run_result, run_error) for explain-run handlers.

    Uses metadata.run_selector:
      - "current": canvas in-memory run
      - "latest" / default: DB lookup by workflow_name or run_id
    """
    meta = route_metadata or {}
    selector = str(meta.get("run_selector") or "").strip().lower()
    run_id = meta.get("run_id")
    workflow_name = meta.get("workflow_name")

    if selector == "current" and canvas_run_log:
        wf = canvas_workflow or {}
        if workflow_name and not wf.get("name"):
            resolved = get_workflow_by_name_db(str(workflow_name), get_current_user_id())
            if resolved:
                wf = resolved
        return wf, list(canvas_run_log), canvas_run_result, canvas_run_error

    if run_id:
        row = get_run_log_db(str(run_id))
        if row:
            return _row_to_context(row, workflow_name)

    if workflow_name:
        logs = list_db_run_logs(limit=20, user_id=get_current_user_id(), workflow=str(workflow_name))
        if logs:
            return _row_to_context(logs[0], workflow_name)

    if canvas_run_log:
        wf = canvas_workflow or {}
        if workflow_name:
            resolved = get_workflow_by_name_db(str(workflow_name), get_current_user_id())
            if resolved:
                wf = resolved
        return wf, list(canvas_run_log), canvas_run_result, canvas_run_error

    wf = canvas_workflow or {}
    if workflow_name:
        resolved = get_workflow_by_name_db(str(workflow_name))
        if resolved:
            wf = resolved
    return wf, [], None, None


def _row_to_context(
    row: dict[str, Any],
    workflow_name: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None, str | None]:
    wf_name = workflow_name or row.get("workflow") or ""
    workflow = get_workflow_by_name_db(str(wf_name), get_current_user_id()) if wf_name else None
    if not workflow:
        workflow = {"name": row.get("workflow") or wf_name or "Workflow", "nodes": [], "edges": []}
    run_log = row.get("run_log") or []
    if not isinstance(run_log, list):
        run_log = []
    run_result = row.get("run_result") if isinstance(row.get("run_result"), dict) else None
    run_error = row.get("run_error") or row.get("error")
    return workflow, run_log, run_result, str(run_error) if run_error else None


def parse_workflow_data(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}
