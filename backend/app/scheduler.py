from __future__ import annotations

import asyncio
import logging
import copy
from datetime import datetime, timezone, timedelta
import os
import json
from pathlib import Path

from app.run_log_capture import apply_report_download, build_run_log_entry, collect_stream_run
from app.database import (
    list_automations,
    append_automation_run,
    list_automation_runs,
    get_workflow_db,
    upsert_run_artifacts,
)
from app.routers.library import append_run_log

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS_DIR = _BACKEND_ROOT / "workflows"

_DEFAULT_ALERT_PAYLOAD = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "currency_pair": "EUR/USD",
    "alert_date": datetime.utcnow().strftime("%Y-%m-%d"),
    "alert_id": "AUTO-0001",
    "event_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
}

_scheduler_task: asyncio.Task | None = None
_last_run_minute: dict[str, str] = {}  # Tracks last run minute for cron: {automation_id: "YYYY-MM-DD HH:MM"}


def match_cron(cron_expr: str, dt: datetime) -> bool:
    """Matches a 5-field cron expression against a datetime in UTC."""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False
    
    def match_part(part: str, val: int) -> bool:
        if part == '*':
            return True
        if ',' in part:
            return any(match_part(sub, val) for sub in part.split(','))
        if '/' in part:
            base, step = part.split('/')
            step_val = int(step)
            if base == '*':
                return val % step_val == 0
            return (val - int(base)) % step_val == 0
        if '-' in part:
            start, end = map(int, part.split('-'))
            return start <= val <= end
        return int(part) == val

    try:
        return (
            match_part(parts[0], dt.minute) and
            match_part(parts[1], dt.hour) and
            match_part(parts[2], dt.day) and
            match_part(parts[3], dt.month) and
            match_part(parts[4], dt.weekday())  # Monday = 0
        )
    except Exception:
        return False


def _resolve_workflow_mock_csv_paths(dag: dict) -> dict:
    """Ensures mock CSV paths in the DAG are absolute and relative to backend root."""
    out = copy.deepcopy(dag)
    for node in out.get("nodes", []):
        cfg = node.get("config")
        if not isinstance(cfg, dict):
            continue
        p = cfg.get("mock_csv_path")
        if not p or not isinstance(p, str):
            continue
        if os.path.isabs(p) and os.path.isfile(p):
            continue
        candidate = (_BACKEND_ROOT / p).resolve()
        try:
            candidate.relative_to(_BACKEND_ROOT)
        except ValueError:
            continue
        if candidate.is_file():
            cfg["mock_csv_path"] = str(candidate)
    return out


def apply_output_overrides(dag: dict, pattern: str | None, run_id: str, dt: datetime) -> dict:
    """
    Applies custom output overrides to output nodes (excel_output, csv_output) within the DAG.
    If pattern is provided, resolves `{timestamp}` and `{run_id}`.
    If pattern is not provided, defaults to suffixing the base filename with `_{run_id}`.
    """
    import copy
    
    out = copy.deepcopy(dag)
    timestamp_str = dt.strftime("%Y%m%d_%H%M%S")
    
    for node in out.get("nodes", []):
        node_type = node.get("type", "")
        # Check if this is an output node with a config and a filename
        if node_type in ("excel_output", "csv_output") or (isinstance(node.get("config"), dict) and "filename" in node["config"]):
            cfg = node.get("config")
            if not isinstance(cfg, dict):
                continue
            
            filename = cfg.get("filename")
            if not filename or not isinstance(filename, str):
                continue
                
            base, ext = os.path.splitext(filename)
            if pattern:
                new_name = pattern
                new_name = new_name.replace("{timestamp}", timestamp_str)
                new_name = new_name.replace("{run_id}", run_id)
                # If the pattern doesn't specify the extension, append the original extension
                if not os.path.splitext(new_name)[1] and ext:
                    new_name = new_name + ext
            else:
                # Default behavior: append suffix to the filename
                new_name = f"{base}_{run_id}{ext}"
                
            cfg["filename"] = new_name
            
    return out


async def execute_automation_workflow(automation: dict) -> None:
    """Loads and executes the workflow associated with the automation."""
    automation_id = automation["id"]
    filename = automation["workflow_filename"]
    owner_id = str(automation.get("user_id") or "").strip()
    row = get_workflow_db(filename, owner_id) if owner_id else None
    if not row or not row.get("workflow_data"):
        err_msg = f"Workflow not found in database: {filename}"
        logger.error(err_msg)
        append_automation_run(
            run_id=f"err_{int(datetime.utcnow().timestamp())}",
            automation_id=automation_id,
            status="error",
            triggered_at=datetime.utcnow(),
            duration_ms=0,
            error=err_msg
        )
        return

    try:
        dag = json.loads(row["workflow_data"])
    except Exception as exc:
        err_msg = f"Failed to parse workflow JSON: {exc}"
        logger.error(err_msg)
        append_automation_run(
            run_id=f"err_{int(datetime.utcnow().timestamp())}",
            automation_id=automation_id,
            status="error",
            triggered_at=datetime.utcnow(),
            duration_ms=0,
            error=err_msg
        )
        return

    started = datetime.utcnow()
    workflow_name = dag.get("name") or dag.get("id") or filename
    node_count = len(dag.get("nodes", []) or [])
    edge_count = len(dag.get("edges", []) or [])
    
    dag = _resolve_workflow_mock_csv_paths(dag)
    run_id = f"auto_r_{int(started.timestamp() * 1000)}"
    pattern = automation.get("output_filename_pattern")
    dag = apply_output_overrides(dag, pattern, run_id, started)

    try:
        node_event_log, run_result, run_error, _total_ms, stream_run_id = collect_stream_run(dag, _DEFAULT_ALERT_PAYLOAD)
        finished = datetime.utcnow()
        duration_ms = int((finished - started).total_seconds() * 1000)
        if stream_run_id:
            run_id = stream_run_id

        if run_error or not run_result:
            err_msg = (run_error or "Automation workflow failed")[:500]
            append_run_log(
                build_run_log_entry(
                    run_id=run_id,
                    workflow=f"[Auto] {workflow_name}",
                    started_at=started,
                    finished_at=finished,
                    status="error",
                    node_count=node_count,
                    edge_count=edge_count,
                    error=err_msg,
                    run_log=node_event_log,
                    run_result=run_result,
                    run_error=err_msg,
                )
            )
            append_automation_run(
                run_id=run_id,
                automation_id=automation_id,
                status="error",
                triggered_at=started,
                duration_ms=duration_ms,
                error=err_msg,
            )
            logger.error(f"Automation '{automation['name']}' run failed: {err_msg}")
            return

        report_path, download_url = apply_report_download(run_result)

        append_run_log(
            build_run_log_entry(
                run_id=run_id,
                workflow=f"[Auto] {workflow_name}",
                started_at=started,
                finished_at=finished,
                status="success",
                node_count=node_count,
                edge_count=edge_count,
                disposition=(run_result or {}).get("disposition"),
                flag_count=(run_result or {}).get("flag_count"),
                report_path=report_path,
                download_url=download_url,
                run_log=node_event_log,
                run_result=run_result,
                run_error=None,
            )
        )

        if download_url:
            upsert_run_artifacts(
                run_id,
                [
                    {
                        "source_node_id": None,
                        "file_name": Path(download_url).name,
                        "file_path": report_path,
                        "download_url": download_url,
                        "generated_at": finished.isoformat() + "Z",
                    }
                ],
            )

        append_automation_run(
            run_id=run_id,
            automation_id=automation_id,
            status="success",
            triggered_at=started,
            duration_ms=duration_ms,
            error=None,
            download_url=download_url
        )
        logger.info(f"Automation '{automation['name']}' run completed successfully: {run_id}")
    except Exception as exc:
        finished = datetime.utcnow()
        duration_ms = int((finished - started).total_seconds() * 1000)
        err_msg = str(exc)[:500]

        # Append run log globally as error
        append_run_log(
            build_run_log_entry(
                run_id=run_id,
                workflow=f"[Auto] {workflow_name}",
                started_at=started,
                finished_at=finished,
                status="error",
                node_count=node_count,
                edge_count=edge_count,
                error=err_msg,
                run_log=[],
                run_result=None,
                run_error=err_msg,
            )
        )

        # Append run log specifically to this automation as error
        append_automation_run(
            run_id=run_id,
            automation_id=automation_id,
            status="error",
            triggered_at=started,
            duration_ms=duration_ms,
            error=err_msg
        )
        logger.error(f"Automation '{automation['name']}' run failed: {err_msg}")


async def _scheduler_loop() -> None:
    """Periodic loop evaluating schedules and triggering executions."""
    logger.info("dbSherpa Automation Scheduler loop started.")
    while True:
        try:
            now_utc = datetime.utcnow()
            active_automations = [a for a in list_automations() if a["active"]]

            for auto in active_automations:
                auto_id = auto["id"]
                stype = auto["schedule_type"]

                if stype == "cron":
                    cron_expr = auto["cron_expression"] or "0 * * * *"
                    if match_cron(cron_expr, now_utc):
                        minute_key = now_utc.strftime("%Y-%m-%d %H:%M")
                        if _last_run_minute.get(auto_id) != minute_key:
                            _last_run_minute[auto_id] = minute_key
                            logger.info(f"Cron trigger fired for automation '{auto['name']}'")
                            # Non-blocking async execution
                            asyncio.create_task(execute_automation_workflow(auto))

                elif stype == "interval":
                    interval_mins = auto["interval_mins"] or 2
                    duration_mins = auto["duration_mins"] or 30
                    
                    created_at_str = auto["created_at"]
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except Exception:
                        created_at = now_utc

                    # Check if duration limit is still active
                    if now_utc <= created_at + timedelta(minutes=duration_mins):
                        runs = list_automation_runs(auto_id, limit=1)
                        should_run = False
                        
                        if not runs:
                            # Never run before, trigger first run
                            should_run = True
                        else:
                            last_run = runs[0]
                            last_triggered_str = last_run["triggered_at"]
                            try:
                                # SQLite stores datetime as text
                                if "Z" in last_triggered_str:
                                    last_triggered_str = last_triggered_str.replace("Z", "")
                                last_triggered = datetime.fromisoformat(last_triggered_str)
                            except Exception:
                                last_triggered = now_utc - timedelta(days=1)
                                
                            if now_utc >= last_triggered + timedelta(minutes=interval_mins):
                                should_run = True
                                
                        if should_run:
                            logger.info(f"Interval trigger fired for automation '{auto['name']}'")
                            asyncio.create_task(execute_automation_workflow(auto))
                            
        except Exception as e:
            logger.exception("Exception in dbSherpa Automation Scheduler loop")
            
        await asyncio.sleep(10)


def start_scheduler() -> None:
    """Launches the scheduler task in the running loop."""
    global _scheduler_task
    if _scheduler_task is None:
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Automation Scheduler task spawned.")


def stop_scheduler() -> None:
    """Stops and cleans up the scheduler task."""
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Automation Scheduler task cancelled.")
