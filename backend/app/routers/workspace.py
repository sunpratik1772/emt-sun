"""Workspace-wide reset — one endpoint to wipe user workload data."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth_deps import require_user_id
from app.database import clear_all_workspace_data
from app.routers.library import append_audit_log, clear_audit_logs, clear_run_logs

router = APIRouter(tags=["workspace"])


@router.delete("/workspace")
def clear_workspace(user_id: str = Depends(require_user_id)) -> dict:
    """Clear chats, workflows, drafts, runs, automations, and log files.

    Preserves user accounts/sessions. Studio ``good_examples/`` demos are
    filesystem-only and are never touched.
    """
    deleted = clear_all_workspace_data(user_id)
    clear_run_logs()
    clear_audit_logs()
    append_audit_log(
        {
            "actor": "user",
            "action": "workspace.clear",
            "detail": f"cleared tables: {deleted}",
            "status": "ok",
        }
    )
    return {
        "ok": True,
        "deleted": deleted,
        "preserved": ["users", "user_sessions", "good_examples"],
    }
