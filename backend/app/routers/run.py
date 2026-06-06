"""Workflow execution — blocking, streaming, and one-click demo variants.

All endpoints run the deterministic validator before touching the DAG
runner so a malformed workflow fails fast with a structured error
payload instead of blowing up half-way through execution.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from engine import RunContext
from engine.jobs import get_default_runner
from copilot.preflight import preflight_dag
from engine.copilot_validate import validate_dag_for_api
from engine.workflow_format import workflow_from_yaml

from ..database import get_workflow_db
from ..deps import GOOD_EXAMPLES_DIR, WORKFLOWS_DIR
from ..run_log_capture import apply_report_download, build_run_log_entry, collect_stream_run
from ..schemas import RunWorkflowRequest
from .library import append_run_log

logger = logging.getLogger(__name__)
router = APIRouter(tags=["run"])

# backend/ — used to resolve `demo_data/...` mock_csv_path regardless of process cwd
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _resolve_workflow_mock_csv_paths(dag: dict) -> dict:
    """
    When the UI posts the same JSON as `backend/workflows/*.json`, relative
    `mock_csv_path` values must find CSVs under `backend/` even if uvicorn
    was started from the repo root. Deep-copy the DAG and rewrite paths that
    exist as `backend/<path>` to absolute paths; leave unknown paths unchanged.
    """
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


# Sensible defaults for the demo endpoint so a reviewer can curl the
# URL with an empty body and still get a meaningful run.
_DEMO_WORKFLOW_FILENAME = "fx_fro_v2_workflow.json"
_DEMO_ALERT_PAYLOAD: dict[str, str] = {
    "trader_id": "T001",
    "book": "FX-SPOT",
    "currency_pair": "EUR/USD",
    "alert_date": "2024-01-15",
    "alert_id": "DEMO-0001",
    "event_time": "2024-01-15 09:00",
}


class RunDemoRequest(BaseModel):
    """
    Body for `POST /run/demo`. All fields optional — a blank body
    runs the bundled FX front-running workflow against the shipped
    CSV fixtures and returns the generated xlsx as an attachment.
    """

    workflow_filename: str = Field(
        default=_DEMO_WORKFLOW_FILENAME,
        description=(
            "Name of a .json/.yaml workflow file under `backend/workflows/` to execute. "
            "Defaults to the bundled demo workflow. `fxfronew_workflow.json` is "
            "the same DAG with report `output/fxfronew_report.xlsx`."
        ),
    )
    alert_payload: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional override of the canned alert payload.",
    )
    return_json: bool = Field(
        default=False,
        description=(
            "If true, return the normal JSON run result (with "
            "`download_url`) instead of streaming the xlsx. Handy for "
            "inspecting the pipeline output without downloading."
        ),
    )


@router.post("/run")
def run(req: RunWorkflowRequest) -> dict:
    """Execute a workflow DAG synchronously. Returns run summary."""
    # Deterministic pre-flight. Errors short-circuit with HTTP 422 and
    # the same payload shape the /validate endpoint returns, so the
    # frontend handles both uniformly.
    started = datetime.now(timezone.utc)
    workflow_name = req.dag.get("name") or req.dag.get("id")
    node_count = len(req.dag.get("nodes", []) or [])
    edge_count = len(req.dag.get("edges", []) or [])

    dag = _resolve_workflow_mock_csv_paths(req.dag)
    dag, validation = preflight_dag(dag)
    if not validation.valid:
        run_log_entry = build_run_log_entry(
            run_id=f"v_{int(started.timestamp() * 1000)}",
            workflow=workflow_name,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            status="error",
            node_count=node_count,
            edge_count=edge_count,
            error="validation_failed",
            run_log=[],
            run_result=None,
            run_error="Validation failed",
        )
        append_run_log(run_log_entry)
        raise HTTPException(status_code=422, detail=validation.to_json())

    try:
        node_event_log, run_result, run_error, _total_ms, stream_run_id = collect_stream_run(dag, req.alert_payload)
        if run_error and not run_result:
            finished = datetime.now(timezone.utc)
            append_run_log(
                build_run_log_entry(
                    run_id=stream_run_id or f"e_{int(started.timestamp() * 1000)}",
                    workflow=workflow_name,
                    started_at=started,
                    finished_at=finished,
                    status="error",
                    node_count=node_count,
                    edge_count=edge_count,
                    error=(run_error or "")[:500],
                    run_log=node_event_log,
                    run_result=run_result,
                    run_error=(run_error or "")[:500],
                )
            )
            raise HTTPException(status_code=500, detail=run_error)

        result: dict = dict(run_result or {})
        apply_report_download(result)
        if validation.warnings:
            result["warnings"] = [w.to_json() for w in validation.warnings]

        finished = datetime.now(timezone.utc)
        append_run_log(
            build_run_log_entry(
                run_id=result.get("run_id") or stream_run_id or f"r_{int(started.timestamp() * 1000)}",
                workflow=workflow_name,
                started_at=started,
                finished_at=finished,
                status="warning" if validation.warnings else "success",
                node_count=node_count,
                edge_count=edge_count,
                disposition=result.get("disposition"),
                flag_count=result.get("flag_count"),
                report_path=result.get("report_path"),
                download_url=result.get("download_url"),
                run_log=node_event_log,
                run_result=result,
                run_error=None,
            )
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        append_run_log(
            build_run_log_entry(
                run_id=f"e_{int(started.timestamp() * 1000)}",
                workflow=workflow_name,
                started_at=started,
                finished_at=finished,
                status="error",
                node_count=node_count,
                edge_count=edge_count,
                error=str(exc)[:500],
                run_log=[],
                run_result=None,
                run_error=str(exc)[:500],
            )
        )
        logger.exception("Workflow run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/run/stream")
def run_stream(req: RunWorkflowRequest) -> StreamingResponse:
    """Execute a workflow and stream per-node events as Server-Sent Events.

    If the DAG fails validation the stream emits a single
    `workflow_error` frame with the validation payload and closes,
    rather than raising HTTP 422. That way the frontend — which is
    already parsing SSE — gets a uniform error surface.
    """
    started = datetime.now(timezone.utc)
    workflow_name = req.dag.get("name") or req.dag.get("id")
    node_count = len(req.dag.get("nodes", []) or [])
    edge_count = len(req.dag.get("edges", []) or [])

    dag = _resolve_workflow_mock_csv_paths(req.dag)
    dag, validation = preflight_dag(dag)

    def event_source():
        node_event_log: list[dict[str, Any]] = []
        if not validation.valid:
            finished = datetime.now(timezone.utc)
            append_run_log(
                build_run_log_entry(
                    run_id=f"v_{int(started.timestamp() * 1000)}",
                    workflow=workflow_name,
                    started_at=started,
                    finished_at=finished,
                    status="error",
                    node_count=node_count,
                    edge_count=edge_count,
                    error="validation_failed",
                    run_log=[],
                    run_result=None,
                    run_error="Validation failed",
                )
            )
            yield "data: " + json.dumps(
                {
                    "type": "workflow_error",
                    "error": "Validation failed",
                    "validation": validation.to_json(),
                }
            ) + "\n\n"
            return

        run_id: str | None = None
        disposition: str | None = None
        flag_count: int | None = None
        report_path: str | None = None
        download_url: str | None = None
        error_text: str | None = None
        run_result_payload: dict[str, Any] | None = None
        try:
            for ev in get_default_runner().stream(dag, req.alert_payload):
                ev_type = ev.get("type")
                if ev_type in {"node_start", "node_complete", "node_error"}:
                    node_event_log.append(
                        {
                            "node_id": ev.get("node_id"),
                            "node_type": ev.get("node_type"),
                            "label": ev.get("label") or ev.get("node_id"),
                            "index": ev.get("index"),
                            "total": ev.get("total"),
                            "status": "running" if ev_type == "node_start" else "ok" if ev_type == "node_complete" else "error",
                            "started_at": ev.get("started_at"),
                            "duration_ms": ev.get("duration_ms"),
                            "input": ev.get("input"),
                            "output": ev.get("output"),
                            "error": ev.get("error"),
                            "trace": ev.get("trace"),
                        }
                    )

                if ev.get("type") == "workflow_complete":
                    res = dict(ev.get("result") or {})
                    persisted = res.pop("persisted_run_log", None)
                    if isinstance(persisted, list) and persisted:
                        node_event_log = persisted
                    report_path, download_url = apply_report_download(res)
                    ev = {**ev, "result": res}
                    run_result_payload = res
                    if validation.warnings:
                        ev = {**ev, "warnings": [w.to_json() for w in validation.warnings]}
                    run_id = res.get("run_id")
                    disposition = res.get("disposition")
                    flag_count = res.get("flag_count")
                if ev.get("type") == "workflow_error":
                    error_text = ev.get("error") or "workflow error"
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as exc:
            error_text = str(exc)[:500]
            logger.exception("Workflow stream run failed")
            yield "data: " + json.dumps(
                {"type": "workflow_error", "error": error_text}
            ) + "\n\n"
        finally:
            finished = datetime.now(timezone.utc)
            status = (
                "error"
                if error_text
                else "warning"
                if validation.warnings
                else "success"
            )
            append_run_log(
                build_run_log_entry(
                    run_id=run_id or f"r_{int(started.timestamp() * 1000)}",
                    workflow=workflow_name,
                    started_at=started,
                    finished_at=finished,
                    status=status,
                    node_count=node_count,
                    edge_count=edge_count,
                    disposition=disposition,
                    flag_count=flag_count,
                    report_path=report_path,
                    download_url=download_url,
                    error=error_text,
                    run_log=node_event_log,
                    run_result=run_result_payload,
                    run_error=error_text,
                )
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _load_bundled_workflow(filename: str) -> dict:
    """
    Read a workflow from the configured workflows dir.

    Only basenames are accepted — this endpoint deliberately doesn't
    let callers escape the directory via `../`. Any suspicious path
    surfaces as a 400, not a 404, so the operator sees intent rather
    than a generic "file missing".
    """
    safe = Path(filename).name  # strips any leading path segments
    if safe != filename:
        raise HTTPException(status_code=400, detail="workflow_filename must be a bare filename")

    from ..request_context import get_current_user_id

    row = get_workflow_db(safe, get_current_user_id())
    if row and row.get("workflow_data"):
        try:
            return json.loads(row["workflow_data"])
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail=f"workflow '{safe}' is not valid JSON: {exc}")

    for base in (GOOD_EXAMPLES_DIR, WORKFLOWS_DIR):
        path = base / safe
        if not path.exists():
            continue
        try:
            text = path.read_text()
            if path.suffix == ".json":
                return json.loads(text)
            if path.suffix in {".yaml", ".yml"}:
                return workflow_from_yaml(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail=f"workflow '{safe}' is not valid JSON: {exc}")
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=f"workflow '{safe}' is not valid YAML: {exc}")

    raise HTTPException(status_code=404, detail=f"workflow '{safe}' not found")


@router.post("/run/demo")
def run_demo(req: Optional[RunDemoRequest] = None):
    """
    One-click demo: run a bundled workflow end-to-end against the CSV
    fixtures in `backend/demo_data/` and return the generated xlsx as
    a browser download.

    This endpoint is the fastest way to verify a deployment end-to-end
    — no alert payload, no workflow authoring file, no external data source
    required. Reviewers can `curl -OJ $SERVICE_URL/run/demo` and open
    the resulting xlsx. Pass `return_json=true` in the body to get the
    normal JSON run summary instead (with a `download_url` field).
    """
    req = req or RunDemoRequest()
    dag = _resolve_workflow_mock_csv_paths(_load_bundled_workflow(req.workflow_filename))
    alert = req.alert_payload or dict(_DEMO_ALERT_PAYLOAD)

    dag, validation = preflight_dag(dag)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.to_json())

    try:
        ctx: RunContext = get_default_runner().run(dag, alert).context
    except Exception as exc:
        logger.exception("Demo run failed (workflow=%s)", req.workflow_filename)
        raise HTTPException(status_code=500, detail=str(exc))

    if not ctx.report_path:
        # Workflow didn't write a report — fall back to JSON so the
        # caller still sees a successful run and can inspect the
        # datasets / sections.
        return {
            "run_id": ctx.run_id,
            "disposition": ctx.disposition,
            "flag_count": ctx.get("flag_count", 0),
            "datasets": list(ctx.datasets.keys()),
            "executive_summary": ctx.executive_summary,
            "note": "workflow produced no report file",
        }

    if req.return_json:
        return {
            "run_id": ctx.run_id,
            "disposition": ctx.disposition,
            "flag_count": ctx.get("flag_count", 0),
            "output_branch": ctx.output_branch,
            "report_path": ctx.report_path,
            "download_url": f"/report/{Path(ctx.report_path).name}",
            "datasets": list(ctx.datasets.keys()),
            "executive_summary": ctx.executive_summary,
        }

    # Default: stream the xlsx back as a download so `curl -OJ` works.
    # The run_id and disposition are attached as response headers so
    # curl -i / browser devtools can still correlate the run with
    # backend logs without parsing the xlsx.
    report_path = Path(ctx.report_path)
    if not report_path.exists():
        raise HTTPException(status_code=500, detail=f"report path missing after run: {report_path}")
    return FileResponse(
        str(report_path),
        filename=report_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{report_path.name}"',
            "X-Run-Id": ctx.run_id,
            "X-Disposition": ctx.disposition or "",
            "X-Flag-Count": str(ctx.get("flag_count", 0)),
            "X-Content-Type-Options": "nosniff",
        },
    )
