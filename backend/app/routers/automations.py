from __future__ import annotations

import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth_deps import feature_guard, require_user, require_user_id
from app.database import (
    list_automations,
    get_automation,
    save_automation,
    delete_automation,
    list_automation_runs,
    delete_automation_run,
    clear_automation_runs,
)
from app.scheduler import execute_automation_workflow

logger = logging.getLogger(__name__)
router = APIRouter(tags=["automations"])


class AutomationPayload(BaseModel):
    name: str = Field(..., description="The name of the automation.")
    workflow_filename: str = Field(..., description="Workflow JSON file to run.")
    schedule_type: str = Field("cron", description="Schedule type: 'cron' or 'interval'.")
    cron_expression: Optional[str] = Field("0 11 * * *", description="Standard 5-field cron string.")
    interval_mins: Optional[int] = Field(2, description="Interval in minutes (if schedule_type is 'interval').")
    duration_mins: Optional[int] = Field(30, description="Active duration in minutes (if schedule_type is 'interval').")
    active: bool = Field(True, description="Active toggle status.")
    author: Optional[str] = Field("Shalini Barman Roy", description="Author of the automation.")
    output_filename_pattern: Optional[str] = Field(None, description="Optional pattern or override for the output filename.")


@router.get("/automations")
def get_all_automations(user_id: str = Depends(feature_guard("automations"))) -> dict:
    """Retrieve all defined automations."""
    try:
        autos = list_automations(user_id)
        return {"automations": autos}
    except Exception as exc:
        logger.exception("Failed to retrieve automations")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/automations/{automation_id}")
def get_single_automation(automation_id: str, user_id: str = Depends(feature_guard("automations"))) -> dict:
    """Retrieve a single automation by ID."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    return auto


@router.post("/automations")
def create_new_automation(
    req: AutomationPayload,
    user: dict = Depends(require_user),
    user_id: str = Depends(feature_guard("automations")),
) -> dict:
    """Create a new scheduled automation."""
    import uuid
    new_id = f"auto_{uuid.uuid4().hex[:12]}"
    try:
        save_automation(
            automation_id=new_id,
            name=req.name,
            workflow_filename=req.workflow_filename,
            schedule_type=req.schedule_type,
            cron_expression=req.cron_expression,
            interval_mins=req.interval_mins,
            duration_mins=req.duration_mins,
            active=req.active,
            author=req.author or user.get("name") or "User",
            user_id=user_id,
            output_filename_pattern=req.output_filename_pattern,
        )
        return {"ok": True, "id": new_id}
    except Exception as exc:
        logger.exception("Failed to create automation")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/automations/{automation_id}")
def update_existing_automation(
    automation_id: str,
    req: AutomationPayload,
    user_id: str = Depends(feature_guard("automations")),
) -> dict:
    """Update an existing automation."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        save_automation(
            automation_id=automation_id,
            name=req.name,
            workflow_filename=req.workflow_filename,
            schedule_type=req.schedule_type,
            cron_expression=req.cron_expression,
            interval_mins=req.interval_mins,
            duration_mins=req.duration_mins,
            active=req.active,
            author=req.author or auto.get("author") or "User",
            user_id=user_id,
            output_filename_pattern=req.output_filename_pattern,
        )
        return {"ok": True}
    except Exception as exc:
        logger.exception(f"Failed to update automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/automations/{automation_id}")
def delete_existing_automation(automation_id: str, user_id: str = Depends(feature_guard("automations"))) -> dict:
    """Delete an automation configuration."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        delete_automation(automation_id, user_id)
        return {"ok": True}
    except Exception as exc:
        logger.exception(f"Failed to delete automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/automations/{automation_id}/run")
def trigger_automation_manually(
    automation_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(feature_guard("automations")),
) -> dict:
    """Trigger an execution run of this automation manually (on-demand)."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        # Trigger non-blocking execution via BackgroundTasks
        background_tasks.add_task(execute_automation_workflow, auto)
        return {"ok": True, "message": "Manual trigger started in the background."}
    except Exception as exc:
        logger.exception(f"Failed to manually trigger automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/automations/{automation_id}/runs")
def get_automation_run_history(
    automation_id: str,
    limit: int = 50,
    user_id: str = Depends(feature_guard("automations")),
) -> dict:
    """Retrieve execution log runs for this automation."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        runs = list_automation_runs(automation_id, limit=limit)
        return {"runs": runs}
    except Exception as exc:
        logger.exception(f"Failed to fetch run logs for automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/automations/{automation_id}/runs/{run_id}")
def delete_single_run(
    automation_id: str,
    run_id: str,
    user_id: str = Depends(feature_guard("automations")),
) -> dict:
    """Delete an individual execution run log."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        delete_automation_run(automation_id, run_id)
        return {"ok": True}
    except Exception as exc:
        logger.exception(f"Failed to delete run {run_id} for automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/automations/{automation_id}/runs")
def clear_all_runs(automation_id: str, user_id: str = Depends(feature_guard("automations"))) -> dict:
    """Clear all execution run logs for this automation."""
    auto = get_automation(automation_id, user_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Automation not found.")
    try:
        clear_automation_runs(automation_id)
        return {"ok": True}
    except Exception as exc:
        logger.exception(f"Failed to clear run logs for automation {automation_id}")
        raise HTTPException(status_code=500, detail=str(exc))
