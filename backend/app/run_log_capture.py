"""Collect per-node run output from the workflow stream for SQLite persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from engine.jobs import get_default_runner


def _node_frame_from_event(ev: dict[str, Any]) -> dict[str, Any] | None:
    ev_type = ev.get("type")
    if ev_type not in {"node_start", "node_complete", "node_error"}:
        return None
    status = (
        "running"
        if ev_type == "node_start"
        else "ok"
        if ev_type == "node_complete"
        else "error"
    )
    frame: dict[str, Any] = {
        "node_id": ev.get("node_id"),
        "node_type": ev.get("node_type"),
        "label": ev.get("label") or ev.get("node_id"),
        "index": ev.get("index"),
        "total": ev.get("total"),
        "status": status,
        "started_at": ev.get("started_at"),
        "duration_ms": ev.get("duration_ms"),
    }
    if ev.get("input") is not None:
        frame["input"] = ev.get("input")
    if ev.get("output") is not None:
        frame["output"] = ev.get("output")
    if ev.get("error") is not None:
        frame["error"] = ev.get("error")
    if ev.get("trace") is not None:
        frame["trace"] = ev.get("trace")
    return frame


def stream_workflow_with_persistence(
    dag: dict,
    alert_payload: dict,
) -> Iterator[dict[str, Any]]:
    """
    Wrap the default runner stream.

    Yields the same SSE events the UI consumes. On ``workflow_complete``,
    attaches ``persisted_run_log`` on the result (full-fidelity snapshots for DB).
    """
    yield from get_default_runner().stream(dag, alert_payload)


def collect_stream_run(
    dag: dict,
    alert_payload: dict,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str | None, int | None, str | None]:
    """
    Execute via stream and return persistence payload.

    Returns:
        run_log, run_result, run_error, total_duration_ms, run_id
    """
    node_event_log: list[dict[str, Any]] = []
    run_result: dict[str, Any] | None = None
    run_error: str | None = None
    total_duration_ms: int | None = None
    run_id: str | None = None

    for ev in get_default_runner().stream(dag, alert_payload):
        ev_type = ev.get("type")
        if ev_type in {"node_start", "node_complete", "node_error"}:
            frame = _node_frame_from_event(ev)
            if frame:
                node_id = frame.get("node_id")
                if ev_type == "node_start":
                    node_event_log.append(frame)
                else:
                    replaced = False
                    for i in range(len(node_event_log) - 1, -1, -1):
                        if node_event_log[i].get("node_id") == node_id:
                            node_event_log[i] = {**node_event_log[i], **frame}
                            replaced = True
                            break
                    if not replaced:
                        node_event_log.append(frame)

        if ev_type == "workflow_complete":
            res = ev.get("result") or {}
            run_id = res.get("run_id")
            run_result = res
            total_duration_ms = ev.get("total_duration_ms")
            persisted = res.pop("persisted_run_log", None)
            if isinstance(persisted, list) and persisted:
                node_event_log = persisted
        elif ev_type == "workflow_error":
            run_error = ev.get("error") or "workflow error"

    # Drop stale node_start-only rows when we have a terminal frame for the same node.
    by_node: dict[str, dict[str, Any]] = {}
    for frame in node_event_log:
        node_id = str(frame.get("node_id") or "")
        if not node_id:
            continue
        prev = by_node.get(node_id)
        if prev is None or prev.get("status") == "running":
            by_node[node_id] = frame
    merged = list(by_node.values())
    if merged:
        merged.sort(key=lambda f: int(f.get("index") or 0))
        node_event_log = merged

    return node_event_log, run_result, run_error, total_duration_ms, run_id


def build_run_log_entry(
    *,
    run_id: str,
    workflow: str | None,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    node_count: int,
    edge_count: int,
    run_log: list[dict[str, Any]] | None = None,
    run_result: dict[str, Any] | None = None,
    run_error: str | None = None,
    disposition: str | None = None,
    flag_count: int | None = None,
    report_path: str | None = None,
    download_url: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    entry: dict[str, Any] = {
        "run_id": run_id,
        "workflow": workflow,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": duration_ms,
        "status": status,
        "node_count": node_count,
        "edge_count": edge_count,
        "run_log": run_log or [],
        "run_result": run_result,
        "run_error": run_error or error,
    }
    if disposition is not None:
        entry["disposition"] = disposition
    if flag_count is not None:
        entry["flag_count"] = flag_count
    if report_path is not None:
        entry["report_path"] = report_path
    if download_url is not None:
        entry["download_url"] = download_url
    if error is not None:
        entry["error"] = error
    return entry


def apply_report_download(result: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not result:
        return None, None
    report_path = result.get("report_path")
    download_url = result.get("download_url")
    if report_path and not download_url:
        download_url = f"/report/{Path(str(report_path)).name}"
        result["download_url"] = download_url
    return report_path, download_url
