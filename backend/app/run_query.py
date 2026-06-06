"""Safe SELECT-only SQL over a materialized run output dataset."""
from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path
from typing import Any

from copilot.run_dataset_memory import load_run_dataset
from engine.output_files import output_dir, safe_filename

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|truncate)\b",
    re.IGNORECASE,
)
_MAX_ROWS = 1000


def _rows_from_run_log(run_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for entry in reversed(run_log):
        output = entry.get("output") if isinstance(entry.get("output"), dict) else {}
        node_output = output.get("node_output") if isinstance(output.get("node_output"), dict) else {}
        rows = node_output.get("rows")
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return list(rows)
    return []


def _rows_from_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for art in artifacts:
        name = str(art.get("file_name") or "")
        if not name.lower().endswith(".csv"):
            continue
        path = output_dir() / safe_filename(name)
        if not path.is_file():
            dl = str(art.get("download_url") or "")
            if dl.startswith("/report/"):
                path = output_dir() / safe_filename(dl.split("/report/", 1)[1])
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                return [dict(row) for row in reader]
    return []


def materialize_run_rows(
    run_row: dict[str, Any],
    workflow: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str]:
    """Load tabular rows for a persisted run. Returns (rows, source_label)."""
    artifacts = run_row.get("artifacts") or []
    if isinstance(artifacts, list):
        rows = _rows_from_artifacts(artifacts)
        if rows:
            return rows, "artifact_csv"

    run_log = run_row.get("run_log") or []
    if isinstance(run_log, list):
        rows = _rows_from_run_log(run_log)
        if rows:
            return rows, "run_log"

    wf = workflow or {"name": run_row.get("workflow") or "Workflow", "nodes": [], "edges": []}
    run_result = run_row.get("run_result") if isinstance(run_row.get("run_result"), dict) else None
    memory = load_run_dataset(wf, run_log if isinstance(run_log, list) else [], run_result)
    rows = memory.get("sample_head") or []
    # load_run_dataset stores full row count but only sample in memory — replay for query
    from copilot.run_dataset_memory import replay_workflow_rows

    replay_rows, note = replay_workflow_rows(wf)
    if replay_rows:
        return replay_rows, note
    return rows, memory.get("source") or "empty"


def execute_run_query(rows: list[dict[str, Any]], sql: str) -> dict[str, Any]:
    """Execute a read-only SQL query against rows loaded into run_output table."""
    query = (sql or "").strip()
    if not query:
        raise ValueError("SQL query is required")
    if ";" in query.rstrip(";"):
        raise ValueError("Only a single SQL statement is allowed")
    query = query.rstrip(";").strip()
    if not query.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")
    if _FORBIDDEN.search(query):
        raise ValueError("Query contains forbidden SQL keywords")

    if not rows:
        return {"columns": [], "rows": [], "row_count": 0}

    conn = sqlite3.connect(":memory:")
    try:
        conn.row_factory = sqlite3.Row
        cols = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
        conn.execute(f"CREATE TABLE run_output ({col_defs})")
        placeholders = ", ".join("?" for _ in cols)
        for row in rows:
            conn.execute(
                f"INSERT INTO run_output VALUES ({placeholders})",
                tuple("" if row.get(c) is None else str(row.get(c)) for c in cols),
            )
        cur = conn.execute(query)
        fetched = cur.fetchmany(_MAX_ROWS + 1)
        if len(fetched) > _MAX_ROWS:
            fetched = fetched[:_MAX_ROWS]
        out_cols = [d[0] for d in (cur.description or [])]
        out_rows = [dict(r) for r in fetched]
        return {"columns": out_cols, "rows": out_rows, "row_count": len(out_rows)}
    finally:
        conn.close()
