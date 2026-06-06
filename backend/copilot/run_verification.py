"""Precomputed run facts and verification SQL for Sherpa run analysis."""
from __future__ import annotations

from typing import Any

from app.run_query import execute_run_query, materialize_run_rows

# Alert-side columns — NULL after a left join means no matching alert row.
_ORPHAN_ALERT_COLUMNS = ("scenario", "alert_date", "alert_trader_name", "description")

_RELIABILITY_TERMS = frozenset(
    {"reliability", "join", "orphan", "coverage", "match", "suggest", "improve"}
)


def _node_output(entry: dict[str, Any]) -> dict[str, Any]:
    output = entry.get("output") if isinstance(entry.get("output"), dict) else {}
    node_output = output.get("node_output") if isinstance(output.get("node_output"), dict) else {}
    return node_output


def _row_count(entry: dict[str, Any]) -> int:
    out = _node_output(entry)
    rows = out.get("rows")
    if isinstance(rows, list):
        return len(rows)
    rc = out.get("rowCount")
    if rc is not None:
        try:
            return int(rc)
        except (TypeError, ValueError):
            pass
    return 0


def compute_run_facts(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
) -> dict[str, Any]:
    """Structured facts from workflow config + run_log (no LLM)."""
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id")): n
        for n in (workflow.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }
    node_facts: dict[str, Any] = {}
    join_facts: list[dict[str, Any]] = []

    for entry in run_log:
        if not isinstance(entry, dict):
            continue
        node_id = str(entry.get("node_id") or "")
        if not node_id:
            continue
        out = _node_output(entry)
        rc = _row_count(entry)
        fact: dict[str, Any] = {
            "label": entry.get("label"),
            "node_type": entry.get("node_type"),
            "status": entry.get("status"),
            "row_count": rc,
        }
        if entry.get("node_type") == "join":
            wf_node = nodes_by_id.get(node_id) or {}
            cfg = wf_node.get("config") or {}
            configured = str(cfg.get("joinType") or "inner").lower()
            executed = str(out.get("joinType") or configured).lower()
            fact["join_type_executed"] = executed
            fact["join_type_configured"] = configured
            fact["left_key"] = out.get("leftKey") or cfg.get("leftKey")
            fact["right_key"] = out.get("rightKey") or cfg.get("rightKey")
            join_facts.append(
                {
                    "node_id": node_id,
                    "label": entry.get("label"),
                    "row_count": rc,
                    "configured_join_type": configured,
                    "executed_join_type": executed,
                    "join_type_mismatch": configured != executed,
                    "left_key": fact["left_key"],
                    "right_key": fact["right_key"],
                }
            )
        node_facts[node_id] = fact

    return {
        "nodes": node_facts,
        "joins": join_facts,
    }


def infer_verification_plan(
    user_message: str | None,
    route_metadata: dict[str, Any] | None,
) -> list[str]:
    """Return ordered verification check ids to run."""
    meta = route_metadata or {}
    plan: list[str] = []
    raw_plan = meta.get("verification_plan")
    if isinstance(raw_plan, list):
        plan.extend(str(p).strip() for p in raw_plan if str(p).strip())

    if meta.get("wants_sql") and "row_counts" not in plan:
        plan.append("row_counts")

    msg = (user_message or "").lower()
    if any(term in msg for term in _RELIABILITY_TERMS):
        for check in ("row_counts", "join_orphans"):
            if check not in plan:
                plan.append(check)

    return plan


def build_verification_queries(
    plan: list[str],
    columns: list[str],
) -> list[dict[str, str]]:
    """Map verification plan ids to safe SELECT statements."""
    colset = set(columns)
    queries: list[dict[str, str]] = []

    if "row_counts" in plan:
        queries.append(
            {
                "check": "row_counts",
                "sql": "SELECT COUNT(*) AS total_rows FROM run_output",
            }
        )

    if "join_orphans" in plan:
        orphan_col = next((c for c in _ORPHAN_ALERT_COLUMNS if c in colset), None)
        if orphan_col:
            queries.append(
                {
                    "check": "join_orphans",
                    "sql": (
                        f'SELECT COUNT(*) AS orphan_rows FROM run_output '
                        f'WHERE "{orphan_col}" IS NULL OR "{orphan_col}" = \'\''
                    ),
                }
            )

    return queries


def run_verification(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
    *,
    user_message: str | None = None,
    route_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Materialize rows, compute facts, execute verification SQL."""
    run_row: dict[str, Any] = {
        "run_log": run_log,
        "workflow": workflow.get("name"),
        "artifacts": (run_result or {}).get("artifacts") or [],
    }
    rows, row_source = materialize_run_rows(run_row, workflow)
    columns = list(rows[0].keys()) if rows else []

    facts = compute_run_facts(workflow, run_log)
    plan = infer_verification_plan(user_message, route_metadata)
    queries = build_verification_queries(plan, columns)

    results: list[dict[str, Any]] = []
    for spec in queries:
        try:
            out = execute_run_query(rows, spec["sql"])
            results.append(
                {
                    "check": spec["check"],
                    "sql": spec["sql"],
                    "ok": True,
                    "rows": out["rows"],
                }
            )
        except ValueError as exc:
            results.append(
                {
                    "check": spec["check"],
                    "sql": spec["sql"],
                    "ok": False,
                    "error": str(exc),
                }
            )

    summary = _summarize_verification(facts, results)

    out: dict[str, Any] = {
        "run_facts": facts,
        "verification_plan": plan,
        "verification_results": results,
        "verification_summary": summary,
        "row_source": row_source,
        "output_row_count": len(rows),
        "output_columns": columns,
    }
    if len(rows) == 0:
        diagnosis = diagnose_empty_output(workflow, run_log)
        if diagnosis:
            out["empty_output_diagnosis"] = diagnosis
    return out


def diagnose_empty_output(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the step that most likely zeroed the pipeline (for run-review next steps)."""
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id")): n
        for n in (workflow.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }
    ordered: list[tuple[str, int, dict[str, Any] | None]] = []
    for entry in run_log:
        if not isinstance(entry, dict):
            continue
        node_id = str(entry.get("node_id") or "")
        if not node_id:
            continue
        ordered.append((node_id, _row_count(entry), nodes_by_id.get(node_id)))

    if not ordered:
        return None

    # First node that went from rows > 0 to 0 (typical filter/join choke point).
    prev = 0
    for node_id, rc, wf_node in ordered:
        if prev > 0 and rc == 0:
            return _diagnosis_record(node_id, rc, wf_node, reason="row_drop")
        prev = rc

    # Entire pipeline empty: prefer the last filter node with 0 rows.
    for node_id, rc, wf_node in reversed(ordered):
        ntype = str((wf_node or {}).get("type") or "")
        if rc == 0 and ntype == "filter":
            return _diagnosis_record(node_id, rc, wf_node, reason="filter_zero")

    last_id, last_rc, last_wf = ordered[-1]
    if last_rc == 0:
        return _diagnosis_record(last_id, last_rc, last_wf, reason="terminal_zero")
    return None


def _diagnosis_record(
    node_id: str,
    row_count: int,
    wf_node: dict[str, Any] | None,
    *,
    reason: str,
) -> dict[str, Any]:
    wf_node = wf_node or {}
    cfg = wf_node.get("config") or {}
    ntype = str(wf_node.get("type") or "")
    label = str(wf_node.get("label") or node_id)
    expression = str(cfg.get("expression") or "").strip()
    return {
        "node_id": node_id,
        "label": label,
        "node_type": ntype,
        "row_count": row_count,
        "reason": reason,
        "expression": expression[:200] if expression else None,
    }


def _summarize_verification(
    facts: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compact interpretation for prompts and deterministic summaries."""
    summary: dict[str, Any] = {
        "total_rows": None,
        "orphan_rows": None,
        "join_type_mismatch": False,
        "suggest_left_join": False,
    }

    for join in facts.get("joins") or []:
        if join.get("join_type_mismatch"):
            summary["join_type_mismatch"] = True

    for result in results:
        if not result.get("ok"):
            continue
        rows = result.get("rows") or []
        if not rows:
            continue
        row = rows[0]
        if result.get("check") == "row_counts":
            summary["total_rows"] = _first_int(row)
        elif result.get("check") == "join_orphans":
            orphans = _first_int(row)
            summary["orphan_rows"] = orphans
            joins = facts.get("joins") or []
            if orphans == 0 and joins:
                configured = str(joins[0].get("configured_join_type") or "").lower()
                if configured == "left":
                    summary["suggest_left_join"] = False
                elif configured == "inner":
                    summary["suggest_left_join"] = False
            elif orphans and orphans > 0:
                summary["suggest_left_join"] = True

    return summary


def _first_int(row: dict[str, Any]) -> int | None:
    for val in row.values():
        try:
            return int(val)
        except (TypeError, ValueError):
            continue
    return None


def format_verification_markdown(verification: dict[str, Any]) -> str:
    """Human-readable block for deterministic summaries."""
    summary = verification.get("verification_summary") or {}
    lines = ["**Verification (deterministic)**"]
    if summary.get("total_rows") is not None:
        lines.append(f"- Output rows: {summary['total_rows']}")
    if summary.get("orphan_rows") is not None:
        lines.append(f"- Join orphan rows (alert-side nulls): {summary['orphan_rows']}")
    if summary.get("join_type_mismatch"):
        lines.append("- Note: configured join type differs from what the run log recorded.")
    if summary.get("orphan_rows") == 0:
        lines.append("- Join coverage: full match on this run (no orphan comms/alerts).")
    diagnosis = verification.get("empty_output_diagnosis")
    if diagnosis:
        label = diagnosis.get("label") or "unknown step"
        lines.append(f"- Likely bottleneck: **{label}** ({diagnosis.get('node_type') or 'node'})")
        if diagnosis.get("expression"):
            lines.append(f"- Filter expression: `{diagnosis['expression'][:100]}`")
    if verification.get("verification_results"):
        for result in verification["verification_results"]:
            if result.get("ok") and result.get("rows"):
                lines.append(f"- `{result['check']}`: {result['rows'][0]}")
    return "\n".join(lines)
