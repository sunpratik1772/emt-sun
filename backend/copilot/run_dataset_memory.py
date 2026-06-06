"""Load workflow output datasets in memory for Sherpa run analysis."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from connectors.registry import get_rows
from engine.dag_runner import topological_sort
from engine.expressions import eval_row
from engine.output_files import output_dir, safe_filename

_MAX_ROWS = 10_000
_MAX_JSON_CHARS = 12_000


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str | None, str | None]:
    src = edge.get("from") or edge.get("source")
    tgt = edge.get("to") or edge.get("target")
    return (
        str(src) if src is not None else None,
        str(tgt) if tgt is not None else None,
    )


def _predecessors(node_id: str, edges: list[dict[str, Any]]) -> list[str]:
    preds: list[str] = []
    for edge in edges:
        src, tgt = _edge_endpoints(edge)
        if tgt == node_id and src:
            preds.append(src)
    return preds


def _parse_select_columns(query: str) -> list[str] | None:
    match = re.search(r"select\s+(.*?)\s+from\b", query, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    clause = match.group(1).strip()
    if clause == "*":
        return None
    return [part.strip().split()[-1] for part in clause.split(",") if part.strip()]


def _filter_columns(rows: list[dict[str, Any]], columns: list[str] | None) -> list[dict[str, Any]]:
    if not columns or not rows:
        return rows
    keep = [c for c in columns if c in rows[0]]
    if not keep:
        return rows
    return [{k: row.get(k) for k in keep} for row in rows]


def _upstream_row_dicts(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def _run_join(
    incoming: dict[str, Any],
    cfg: dict[str, Any],
    *,
    node_id: str = "",
    edges: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    from engine.join_utils import run_join_rows

    rows, _meta = run_join_rows(node_id, incoming, cfg, edges)
    return rows


def _run_sort(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    key = cfg.get("sortBy")
    order = (cfg.get("order") or "asc").lower()
    if not key:
        return rows

    def _sort_key(row: dict[str, Any]) -> tuple[Any, Any]:
        value = row.get(key)
        return (value is None, value)

    return sorted(rows, key=_sort_key, reverse=(order == "desc"))


def replay_workflow_rows(workflow: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Re-execute transform chain from connector sources (db_query → join → sort …)."""
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    if not nodes:
        return [], "no workflow nodes"

    nodes_by_id = {n["id"]: n for n in nodes if isinstance(n, dict) and n.get("id")}
    try:
        order = topological_sort(list(nodes_by_id.values()), edges)
    except Exception as exc:
        return [], f"workflow sort failed: {exc}"

    outputs: dict[str, dict[str, Any]] = {}
    last_rows: list[dict[str, Any]] = []

    for node_id in order:
        node = nodes_by_id[node_id]
        node_type = node.get("type") or ""
        cfg = node.get("config") or {}
        incoming = {
            pred: outputs[pred]
            for pred in _predecessors(node_id, edges)
            if pred in outputs
        }

        if node_type in ("manual_trigger", "schedule", "api_trigger", "webhook_trigger"):
            outputs[node_id] = {"rows": []}
            continue

        if node_type == "db_query":
            source = cfg.get("source")
            rows = get_rows(str(source)) if source else []
            rows = _filter_columns(rows, _parse_select_columns(str(cfg.get("query") or "")))
            payload = {"rows": rows[:_MAX_ROWS], "rowCount": len(rows)}
            outputs[node_id] = payload
            last_rows = payload["rows"]
            continue

        if node_type == "csv_extract":
            source = cfg.get("source")
            rows = get_rows(str(source)) if source else []
            payload = {"rows": rows[:_MAX_ROWS], "rowCount": len(rows)}
            outputs[node_id] = payload
            last_rows = payload["rows"]
            continue

        if node_type == "join":
            rows = _run_join(incoming, cfg, node_id=node_id, edges=edges)[:_MAX_ROWS]
            outputs[node_id] = {"rows": rows, "rowCount": len(rows)}
            last_rows = rows
            continue

        if node_type == "sort":
            rows = _run_sort(_upstream_row_dicts(incoming), cfg)[:_MAX_ROWS]
            outputs[node_id] = {"rows": rows, "rowCount": len(rows)}
            last_rows = rows
            continue

        if node_type == "filter":
            expr = str(cfg.get("expression") or "True")
            rows = [r for r in _upstream_row_dicts(incoming) if eval_row(expr, r)]
            rows = rows[:_MAX_ROWS]
            outputs[node_id] = {
                "rows": rows,
                "rowCount": len(rows),
                "expression": expr,
                "filtered": len(_upstream_row_dicts(incoming)) - len(rows),
            }
            last_rows = rows
            continue

        if node_type in ("map_transform", "select_columns", "deduplicate", "group_by"):
            rows = _upstream_row_dicts(incoming)[:_MAX_ROWS]
            outputs[node_id] = {"rows": rows, "rowCount": len(rows)}
            last_rows = rows
            continue

        if node_type in ("csv_output", "excel_output", "response"):
            rows = _upstream_row_dicts(incoming)[:_MAX_ROWS]
            outputs[node_id] = {"rows": rows, "rowCount": len(rows)}
            last_rows = rows
            continue

    if not last_rows:
        return [], "no tabular rows produced by replay"
    return last_rows, "replayed from workflow sources"


def _resolve_export_path(
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
) -> Path | None:
    if run_result:
        download = str(run_result.get("download_url") or "")
        if download.startswith("/report/"):
            name = download.split("/report/", 1)[1]
            path = output_dir() / safe_filename(name)
            if path.is_file():
                return path
        report_path = run_result.get("report_path")
        if report_path:
            path = Path(str(report_path))
            if path.is_file():
                return path

    for entry in reversed(run_log):
        output = entry.get("output") if isinstance(entry.get("output"), dict) else {}
        node_output = output.get("node_output") if isinstance(output.get("node_output"), dict) else {}
        for key in ("report_path", "filename"):
            raw = node_output.get(key)
            if not raw:
                continue
            path = Path(str(raw))
            if path.is_file():
                return path
            candidate = output_dir() / safe_filename(path.name)
            if candidate.is_file():
                return candidate
    return None


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for idx, row in enumerate(reader):
            if idx >= _MAX_ROWS:
                break
            rows.append(dict(row))
    return rows


def load_run_dataset(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Load the primary result dataset and compute analyst-friendly insights."""
    rows: list[dict[str, Any]] = []
    source = ""

    export_path = _resolve_export_path(run_log, run_result)
    if export_path and export_path.suffix.lower() == ".csv":
        rows = _load_csv_rows(export_path)
        source = f"export_file:{export_path.name}"
    elif export_path:
        source = f"export_file_unsupported:{export_path.name}"

    if not rows:
        rows, replay_note = replay_workflow_rows(workflow)
        source = replay_note

    insights = _compute_insights(rows)
    return {
        "source": source,
        "row_count": len(rows),
        "insights": insights,
        "sample_head": rows[:5],
        "sample_tail": rows[-3:] if len(rows) > 5 else [],
    }


def _compute_insights(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"empty": True}

    insights: dict[str, Any] = {"empty": False}
    columns = list(rows[0].keys())
    insights["columns"] = columns

    trader_col = next((c for c in ("trader_name", "trader_id") if c in columns), None)
    score_col = "relevance_score" if "relevance_score" in columns else None

    if score_col:
        scores = [float(r[score_col]) for r in rows if r.get(score_col) is not None]
        if scores:
            insights["relevance_score_min"] = min(scores)
            insights["relevance_score_max"] = max(scores)

    if trader_col and score_col:
        totals: dict[str, dict[str, Any]] = {}
        for row in rows:
            name = str(row.get(trader_col) or "")
            if not name:
                continue
            score = float(row[score_col]) if row.get(score_col) is not None else 0.0
            bucket = totals.setdefault(name, {"sum": 0.0, "count": 0, "max": 0.0})
            bucket["sum"] += score
            bucket["count"] += 1
            bucket["max"] = max(bucket["max"], score)
        ranked = sorted(
            (
                {
                    trader_col: name,
                    "total_relevance": round(stats["sum"], 4),
                    "message_count": stats["count"],
                    "max_relevance": round(stats["max"], 4),
                }
                for name, stats in totals.items()
            ),
            key=lambda item: item["total_relevance"],
            reverse=True,
        )
        insights["top_traders_by_total_relevance"] = ranked[:10]

    return insights


def format_dataset_memory_markdown(memory: dict[str, Any]) -> str:
    """Compact markdown block for LLM and deterministic summaries."""
    if not memory or memory.get("row_count", 0) == 0:
        return "**Dataset in memory:** no rows loaded."

    lines = [
        "**Dataset in memory**",
        f"- Source: {memory.get('source', 'unknown')}",
        f"- Rows loaded: {memory.get('row_count', 0)}",
    ]
    insights = memory.get("insights") or {}
    if insights.get("relevance_score_min") is not None:
        lines.append(
            f"- Relevance score range: {insights['relevance_score_min']} – {insights['relevance_score_max']}"
        )
    top = insights.get("top_traders_by_total_relevance") or []
    if top:
        lines.append("- Top traders by total relevance:")
        for idx, row in enumerate(top[:5], 1):
            name = row.get("trader_name") or row.get("trader_id") or "?"
            lines.append(
                f"  {idx}. {name}: total={row.get('total_relevance')}, "
                f"messages={row.get('message_count')}, max={row.get('max_relevance')}"
            )
    head = memory.get("sample_head") or []
    if head:
        lines.append(f"- First rows (sample): `{json.dumps(head[:3], default=str)[:800]}`")
    return "\n".join(lines)


def dataset_memory_for_prompt(memory: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe payload slice for the run analyst LLM."""
    blob = {
        "source": memory.get("source"),
        "row_count": memory.get("row_count"),
        "insights": memory.get("insights"),
        "sample_head": (memory.get("sample_head") or [])[:5],
        "sample_tail": (memory.get("sample_tail") or [])[:3],
    }
    text = json.dumps(blob, default=str)
    if len(text) > _MAX_JSON_CHARS:
        blob["truncated"] = True
        blob["sample_head"] = blob["sample_head"][:2]
        blob["sample_tail"] = []
    return blob
