"""Unified workflow + run resolution for Sherpa handlers."""
from __future__ import annotations

from typing import Any

from app.database import get_workflow_by_name_db

from .run_resolver import resolve_run_context


def resolve_workflow_for_edit(
    route_metadata: dict[str, Any] | None,
    *,
    canvas_workflow: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Load the workflow to edit.

    Returns (workflow, error_message). error_message is set when edit was
    requested but no workflow could be loaded.
    """
    meta = route_metadata or {}
    if not meta.get("edit_existing_workflow"):
        return canvas_workflow, None

    # Canvas is always authoritative when it has nodes — never substitute a
    # same-named saved file from the DB (user may have deleted nodes locally).
    if canvas_workflow and (canvas_workflow.get("nodes") or []):
        return canvas_workflow, None

    name = str(meta.get("workflow_name") or "").strip()
    if name:
        from app.request_context import get_current_user_id

        resolved = get_workflow_by_name_db(name, get_current_user_id())
        if resolved and (resolved.get("nodes") or []):
            return resolved, None

    if canvas_workflow:
        return canvas_workflow, None

    return None, (
        f'Could not load workflow "{name or "on canvas"}" for editing. '
        "Open the workflow on the canvas or save it first."
    )


def resolve_sherpa_context(
    route_metadata: dict[str, Any] | None,
    *,
    canvas_workflow: dict[str, Any] | None = None,
    canvas_run_log: list[dict[str, Any]] | None = None,
    canvas_run_result: dict[str, Any] | None = None,
    canvas_run_error: str | None = None,
) -> dict[str, Any]:
    """Single resolver for explain-run and build-edit paths."""
    edit_wf, edit_err = resolve_workflow_for_edit(
        route_metadata,
        canvas_workflow=canvas_workflow,
    )
    workflow, run_log, run_result, run_error = resolve_run_context(
        route_metadata or {},
        canvas_workflow=edit_wf or canvas_workflow,
        canvas_run_log=canvas_run_log,
        canvas_run_result=canvas_run_result,
        canvas_run_error=canvas_run_error,
    )
    return {
        "workflow": workflow,
        "run_log": run_log,
        "run_result": run_result,
        "run_error": run_error,
        "edit_error": edit_err,
        "edit_workflow": edit_wf,
    }
