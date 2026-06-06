"""
DAG runner — executes a workflow definition against a RunContext.

This is the heart of the engine. The contract it implements is small:

  1. Validate the DAG is acyclic (topological_sort raises on cycles).
  2. Walk nodes in topo order; for each, look up its handler in
     `NODE_HANDLERS` and call `handler(node_dict, ctx)`.
  3. After each handler returns, type-check the values it stored at
     each declared output_port (see `_resolve_output_value`). A
     handler that lies about its outputs fails fast — preferable to a
     mysterious KeyError ten nodes downstream.
  4. Stream events (`workflow_start`, `node_start`, `node_complete`,
     `node_error`, `workflow_complete`, `workflow_error`) to anyone
     subscribing through the SSE generator (`run_workflow_stream`).
     The non-streaming `run_workflow` is just the same loop without
     yielding events.

If you're new here:

  * Start at `run_workflow` (bottom of file). It's the canonical
    entry point used by HTTP `/run` and most tests.
  * The `topological_sort` and `_edge_endpoints` helpers are pure
    graph utilities — also used by the validator, hence kept here.
  * Output-port enforcement is pedantic on purpose: it's our only
    automated check that a handler actually produced what its YAML
    declared. Without it, the wiring grammar `{dataset.col.agg}`
    silently breaks two scenarios later.

Nothing in this file knows about specific node types. New nodes plug
in via the registry — no edits needed here.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import traceback
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterator

from .node_spec import NodeSpec

import pandas as pd

from .context import RunContext
from .ports import PortSpec, PortType
from .registry import NODE_HANDLERS, NODE_SPECS  # single source of truth — see registry.py

logger = logging.getLogger(__name__)

# Max rows persisted per dataset/node_output table (full fidelity for run history).
_RUN_LOG_MAX_RECORDS = int(os.environ.get("RUN_LOG_MAX_RECORDS", "5000"))


# ---------------------------------------------------------------------------
# Output port contract enforcement
# ---------------------------------------------------------------------------
def _resolve_output_value(port: PortSpec, node: dict, ctx: RunContext) -> tuple[object, str] | None:
    """
    Find where the handler stored the port's value so we can type-check
    it. Lookup is **type-driven** because each PortType has a different
    storage convention in our handlers:

      DATAFRAME → `ctx.datasets[output_name]` (primary port) or
                  `ctx.datasets[port.name]`.
      SCALAR    → `ctx.values[port.name]`,
                  `ctx.values[f"{output_name}_{port.name}"]` (the
                  `{output_name}_count` / `{output_name}_flag_count`
                  convention), or attribute on ctx.
      TEXT      → `ctx.values[port.name]` or attribute on ctx.

    Returns `(value, location)` or `None` if the port isn't produced
    (allowed when `port.optional` is true).
    """
    cfg = node.get("config", {}) or {}
    output_name = cfg.get("output_name")

    if port.type is PortType.DATAFRAME:
        if port.store_at:
            sa = port.store_at
            m = re.fullmatch(r"datasets\.<(\w+)>", sa)
            if m:
                key = cfg.get(m.group(1))
                if key is not None and str(key) in ctx.datasets:
                    loc = f"ctx.datasets[{key!r}]"
                    return ctx.datasets[str(key)], loc
            m = re.fullmatch(r"datasets\.(\w+)", sa)
            if m and m.group(1) in ctx.datasets:
                loc = f"ctx.datasets[{m.group(1)!r}]"
                return ctx.datasets[m.group(1)], loc
        if output_name and output_name in ctx.datasets:
            return ctx.datasets[output_name], f"ctx.datasets[{output_name!r}]"
        if port.name in ctx.datasets:
            return ctx.datasets[port.name], f"ctx.datasets[{port.name!r}]"
        return None

    if port.type in (PortType.SCALAR, PortType.TEXT):
        if port.name in ctx.values:
            return ctx.values[port.name], f"ctx.values[{port.name!r}]"
        if output_name:
            key = f"{output_name}_{port.name}"
            if key in ctx.values:
                return ctx.values[key], f"ctx.values[{key!r}]"
        attr = getattr(ctx, port.name, None)
        if attr not in (None, ""):
            return attr, f"ctx.{port.name}"
        return None

    return None


def _assert_port_type(port: PortSpec, value: object) -> str | None:
    """Return an error string if `value` doesn't satisfy `port.type`."""
    if port.type is PortType.DATAFRAME:
        if not isinstance(value, pd.DataFrame):
            return f"expected DataFrame, got {type(value).__name__}"
    elif port.type is PortType.SCALAR:
        if not isinstance(value, (int, float, bool)) or isinstance(value, bool):
            # bools are ints in Python; we accept either.
            if not isinstance(value, (int, float)):
                return f"expected scalar (int|float), got {type(value).__name__}"
    elif port.type is PortType.TEXT:
        if not isinstance(value, str):
            return f"expected str, got {type(value).__name__}"
    elif port.type is PortType.OBJECT:
        # n8n-style nodes often pass lists of JSON objects between steps.
        # Treat both dict and list as valid object payloads.
        if not isinstance(value, (dict, list)):
            return f"expected object/dict/list, got {type(value).__name__}"
    return None


def _resolve_object_port_value(
    port: PortSpec, node: dict, ctx: RunContext
) -> tuple[object, str] | None:
    """Locate a stored OBJECT output using `port.store_at` (subset of patterns)."""
    if port.type is not PortType.OBJECT or not port.store_at:
        return None
    cfg = node.get("config") or {}
    sa = port.store_at
    m = re.fullmatch(r"ctx\.sections\[\{(\w+)\}\]", sa)
    if m:
        key = cfg.get(m.group(1))
        if key is None:
            return None
        return ctx.sections.get(key), f"ctx.sections[{key!r}]"
    m = re.fullmatch(r"ctx\.values\[(\w+)\]", sa)
    if m:
        name = m.group(1)
        return ctx.values.get(name), f"ctx.values[{name!r}]"
    return None


def _output_dataframe_required_columns(
    port: PortSpec, spec: NodeSpec, node: dict
) -> tuple[str, ...]:
    """
    Declared columns for a dataframe output port — either static
    `port.required_columns` or `contract.output_columns_by_source` when
    the node opts into source-keyed schemas (see EXECUTION_DATA_COLLECTOR).
    """
    contract = spec.contract or {}
    schema_port = contract.get("source_keyed_schema_port")
    if schema_port and port.name == schema_port:
        by_source = contract.get("output_columns_by_source") or {}
        param = contract.get("source_param_for_schema", "source")
        default = contract.get("source_schema_default")
        cfg = node.get("config") or {}
        source = cfg.get(param, default)
        if source is None:
            source = ""
        cols = by_source.get(str(source), ())
        return tuple(str(c) for c in cols)
    return port.required_columns


def check_input_port_schema(node: dict, ctx: RunContext) -> list[str]:
    """
    Before/after wiring checks: for each input DATAFRAME port that declares
    `required_columns`, ensure the referenced dataset (via
    `source_config_key` or default ``input_name``) exists in ctx and
    contains those columns.

    If the dataset is absent, returns no issues — some nodes pull inputs
    from alternate paths (e.g. scalar fallbacks).
    """
    node_type = node.get("type")
    spec = NODE_SPECS.get(node_type)
    if spec is None:
        return []
    cfg = node.get("config") or {}
    issues: list[str] = []
    for port in spec.input_ports:
        if port.type is not PortType.DATAFRAME or not port.required_columns:
            continue
        key_field = port.source_config_key or "input_name"
        ds_name = cfg.get(key_field)
        if not ds_name:
            continue
        df = ctx.datasets.get(ds_name)
        if df is None:
            continue
        if not isinstance(df, pd.DataFrame):
            issues.append(
                f"input port '{port.name}': expected DataFrame at ctx.datasets[{ds_name!r}], "
                f"got {type(df).__name__}"
            )
            continue
        for col in port.required_columns:
            if col not in df.columns:
                issues.append(
                    f"input port '{port.name}' dataset {ds_name!r}: missing column {col!r}"
                )
    return issues


def check_output_contract(node: dict, ctx: RunContext) -> list[str]:
    """
    After a handler runs, verify the node produced each declared
    non-optional output port with the right runtime type. Returns a
    list of human-readable issue strings (empty on success).

    This is a defence-in-depth check. The pre-flight validator already
    ensures the graph is wired correctly; this catches handlers that
    *claim* to produce a DataFrame but actually drop a scalar in the
    same slot, or forget to write a value altogether. Without this,
    downstream nodes fail later with cryptic KeyErrors.

    OBJECT ports are skipped unless they declare `required_keys` and a
    `store_at` path we can resolve (strict sections / values objects).
    """
    node_type = node.get("type")
    spec = NODE_SPECS.get(node_type)
    if spec is None:
        return []
    issues: list[str] = []
    for port in spec.output_ports:
        if port.type is PortType.OBJECT:
            if not port.required_keys:
                continue
            resolved = _resolve_object_port_value(port, node, ctx)
            if resolved is None:
                if not port.optional:
                    issues.append(
                        f"output port '{port.name}' ({port.type.value}) not produced"
                    )
                continue
            value, location = resolved
            err = _assert_port_type(port, value)
            if err:
                issues.append(f"output port '{port.name}' at {location}: {err}")
                continue
            if not isinstance(value, dict):
                continue
            for rk in port.required_keys:
                if rk not in value:
                    issues.append(
                        f"output port '{port.name}' at {location}: missing key {rk!r}"
                    )
            continue
        resolved = _resolve_output_value(port, node, ctx)
        if resolved is None:
            if not port.optional:
                issues.append(
                    f"output port '{port.name}' ({port.type.value}) not produced"
                )
            continue
        value, location = resolved
        err = _assert_port_type(port, value)
        if err:
            issues.append(f"output port '{port.name}' at {location}: {err}")
            continue
        if (
            port.type is PortType.DATAFRAME
            and port.required_columns
            and isinstance(value, pd.DataFrame)
        ):
            for col in port.required_columns:
                if col not in value.columns:
                    issues.append(
                        f"output port '{port.name}' at {location}: missing column {col!r}"
                    )
    return issues


def _edge_endpoints(edge: dict) -> tuple[str, str]:
    """Accept either {from,to} (dbSherpa native) or {source,target} (ReactFlow / LLM output)."""
    src = edge.get("from") or edge.get("source")
    dst = edge.get("to") or edge.get("target")
    if not src or not dst:
        raise ValueError(f"Edge missing endpoints: {edge!r}")
    return src, dst


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Kahn's algorithm — returns node IDs in execution order."""
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}

    for edge in edges:
        src, dst = _edge_endpoints(edge)
        graph[src].append(dst)
        in_degree[dst] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in graph[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise ValueError("DAG contains a cycle — check your edges")

    return order


def _wire_inputs(node: dict, edges: list[dict], ctx: RunContext) -> None:
    """
    Auto-wire upstream node outputs into the destination node's
    conventional input keys. New n8n-style nodes read from
    ``{node_id}_input`` (or ``_input1`` / ``_input2`` for MERGE).
    Source side: IF emits ``{src}_true`` / ``{src}_false``; SWITCH emits
    ``{src}_outputN``; everything else emits ``{src}_output``.

    Edges may carry ``sourceHandle`` (e.g. "true", "false", "0") and
    ``targetHandle`` (e.g. "input1", "input2") to disambiguate.
    """
    dst = node.get("id")
    if not dst:
        return
    incoming = []
    for edge in edges:
        src, tgt = _edge_endpoints(edge)
        if tgt != dst:
            continue
        incoming.append(
            (
                src,
                edge.get(
                    "sourceHandle",
                    edge.get("from_port", edge.get("branch", edge.get("port"))),
                ),
                edge.get("targetHandle", edge.get("to_port")),
            )
        )

    if not incoming:
        return

    def _norm_handle(raw) -> str | None:
        if raw is None:
            return None
        h = str(raw).strip()
        if not h:
            return None
        # Legacy edge annotations from converted n8n graphs.
        # Examples: "output:0", "output_0", "0", "true", "false".
        if h.startswith("output:"):
            return "output" + h.split(":", 1)[1]
        if h == "main":
            return "true"
        if h == "else":
            return "false"
        if h == "output_0":
            return "output0"
        if h == "output_1":
            return "output1"
        return h

    # Group by target handle. Default target: "input".
    by_target: dict[str, list] = {}
    for src, src_handle, tgt_handle in incoming:
        key = _norm_handle(tgt_handle) or "input"
        by_target.setdefault(key, []).append((src, _norm_handle(src_handle)))

    # Compatibility fallback: many generated graphs omit explicit target
    # handles for 2-input nodes. When all incoming edges collapse into the
    # default "input", split them deterministically into input1/input2.
    node_type = str(node.get("type", ""))
    if (
        node_type in {"MERGE", "COMPARE_DATASETS"}
        and "input" in by_target
        and len(by_target) == 1
        and len(by_target["input"]) >= 2
    ):
        collapsed = by_target.pop("input")
        by_target["input1"] = [collapsed[0]]
        by_target["input2"] = collapsed[1:]

    for tgt_handle, srcs in by_target.items():
        merged: list = []
        for src, src_handle in srcs:
            if src_handle in ("true", "false"):
                upstream = ctx.get(f"{src}_{src_handle}")
            elif src_handle and src_handle.startswith("output"):
                upstream = ctx.get(f"{src}_{src_handle}")
            elif src_handle and src_handle.isdigit():
                upstream = ctx.get(f"{src}_output{src_handle}")
            else:
                upstream = ctx.get(f"{src}_output")
            if upstream is None:
                continue
            if isinstance(upstream, list):
                merged.extend(upstream)
            else:
                merged.append(upstream)
        ctx.set(f"{dst}_{tgt_handle}", merged)


def execute_nodes(nodes: list[dict], edges: list[dict], ctx: RunContext) -> None:
    """
    Run a set of nodes against an existing RunContext.

    Extracted from `run_workflow` so the MAP primitive (and future
    SUB_WORKFLOW / IF primitives) can execute a nested DAG inside the
    same runtime path. Callers own ctx lifecycle — this helper just
    advances it through the nodes in topological order and enforces
    the per-node output contract.
    """
    nodes_by_id = {n["id"]: n for n in nodes}
    order = topological_sort(nodes, edges)
    ctx._active_edges = list(edges)
    ctx.output_map.clear()
    for node_id in order:
        node = nodes_by_id[node_id]
        node_type = node["type"]
        handler = NODE_HANDLERS.get(node_type)
        if not handler:
            raise ValueError(f"Unknown node type '{node_type}' on node '{node_id}'")
        label = node.get("label", node_type)
        logger.info("  → [%s] %s", node_id, label)
        _wire_inputs(node, edges, ctx)
        input_issues = check_input_port_schema(node, ctx)
        if input_issues:
            raise ValueError(
                f"Node '{node_id}' ({node_type}) violated its input contract: "
                + "; ".join(input_issues)
            )
        handler(node, ctx)
        contract_issues = check_output_contract(node, ctx)
        if contract_issues:
            raise ValueError(
                f"Node '{node_id}' ({node_type}) violated its output contract: "
                + "; ".join(contract_issues)
            )


def run_workflow(dag: dict, alert_payload: dict) -> RunContext:
    """Synchronously run a DAG to completion. The standard entry point.

    `dag` is the parsed workflow JSON (nodes + edges). `alert_payload`
    is the immutable input — trader_id, event_time, etc. — that the
    ALERT_TRIGGER node copies into ctx.values.

    Returns the populated RunContext. Inspect `.disposition`,
    `.report_path`, `.sections`, `.executive_summary`, and
    `.datasets[...]` to verify outputs in tests.

    Raises whatever the failing handler raised — the runner does not
    swallow exceptions in the non-streaming path. Use
    `run_workflow_stream` if you want per-node events instead.
    """
    nodes = dag["nodes"]
    edges = dag.get("edges", [])

    ctx = RunContext(alert_payload=alert_payload)

    logger.info(
        "=== dbSherpa Workflow: %s (run_id=%s) ===",
        dag.get("name", dag.get("workflow_id")),
        ctx.run_id,
    )
    logger.info("Execution order: %s", topological_sort(nodes, edges))

    execute_nodes(nodes, edges, ctx)

    logger.info(
        "Workflow complete (run_id=%s). Disposition=%s | Report=%s",
        ctx.run_id,
        ctx.disposition,
        ctx.report_path,
    )
    return ctx


def load_and_run(dag_path: str, alert_payload: dict) -> RunContext:
    with open(dag_path) as f:
        dag = json.load(f)
    return run_workflow(dag, alert_payload)


# ── Streaming execution with per-node events ─────────────────────────────────

def _preview_dataset(df: pd.DataFrame, max_rows: int = 3) -> dict:
    """Small JSON-safe preview of a DataFrame for the UI."""
    try:
        head = df.head(max_rows).copy()
        for col in head.columns:
            if head[col].dtype.kind == "M":  # datetimes
                head[col] = head[col].astype(str)
            elif head[col].apply(lambda v: isinstance(v, (list, dict))).any():
                head[col] = head[col].apply(str)
        return {
            "rows": int(len(df)),
            "columns": list(map(str, df.columns)),
            "sample": head.to_dict(orient="records"),
        }
    except Exception:
        return {"rows": int(len(df)) if df is not None else 0, "columns": [], "sample": []}


def _full_dataset_records(df: pd.DataFrame, max_rows: int | None = None) -> list[dict]:
    """Full JSON-safe DataFrame rows for run history persistence."""
    cap = max_rows if max_rows is not None else _RUN_LOG_MAX_RECORDS
    try:
        full = df.copy()
        for col in full.columns:
            if full[col].dtype.kind in {"M", "m"}:
                full[col] = full[col].astype(str)
            else:
                full[col] = full[col].apply(_jsonable)
        records = full.to_dict(orient="records")
        records = _jsonable(records)
        if isinstance(records, list) and len(records) > cap:
            return records[:cap]
        return records if isinstance(records, list) else []
    except Exception:
        return []


def _snapshot_output(node: dict, ctx: RunContext, before: dict, *, persist: bool = False) -> dict:
    """Describe what changed in the context as a result of executing `node`."""
    node_type = node["type"]
    cfg = node.get("config", {})
    summary: dict = {}

    # New / changed datasets
    new_datasets = {}
    for name, df in ctx.datasets.items():
        sig = (id(df), len(df))
        if before["dataset_sigs"].get(name) != sig:
            if persist:
                preview = _preview_dataset(df, max_rows=3)
                records = _full_dataset_records(df)
                new_datasets[name] = {
                    **preview,
                    "records": records,
                    **({"_rows_truncated": len(df)} if len(df) > len(records) else {}),
                }
            else:
                new_datasets[name] = _preview_dataset(df)
    if new_datasets:
        summary["datasets"] = new_datasets

    # New / changed context values
    new_values = {k: v for k, v in ctx.values.items() if before["values"].get(k) != v}
    if new_values:
        summary["context"] = {k: _jsonable(v) for k, v in new_values.items()}

    agent_response = _agent_response(node, new_values, ctx)
    if agent_response:
        summary["agent_response"] = agent_response

    # Node-type specific highlights
    if node_type == "DECISION_RULE":
        summary["disposition"] = ctx.disposition
        summary["flag_count"] = ctx.get("flag_count", 0)
        summary["output_branch"] = ctx.output_branch
    if node_type == "CONSOLIDATED_SUMMARY":
        es = ctx.executive_summary or ""
        summary["executive_summary_preview"] = es[:400] + ("…" if len(es) > 400 else "")
        summary["executive_summary_chars"] = len(es)
    if node_type == "SECTION_SUMMARY":
        section_name = cfg.get("section_name", "section")
        sec = ctx.sections.get(section_name)
        if sec:
            narrative = sec.get("narrative", "") or ""
            summary["section"] = {
                "name": section_name,
                "stats": _jsonable(sec.get("stats", {})),
                "narrative_preview": narrative[:240] + ("…" if len(narrative) > 240 else ""),
            }
    if node_type == "REPORT_OUTPUT":
        summary["report_path"] = ctx.report_path

    node_id = node.get("id")
    raw = ctx.output_map.get(node_id) if node_id else None
    if isinstance(raw, dict):
        jsonable = _jsonable(raw)
        if isinstance(jsonable, dict):
            rows = jsonable.get("rows")
            if isinstance(rows, list):
                cap = _RUN_LOG_MAX_RECORDS if persist else 25
                if len(rows) > cap:
                    jsonable = {**jsonable, "rows": rows[:cap], "_rows_truncated": len(rows)}
            summary["node_output"] = jsonable

    return summary


def _snapshot_node_inputs(node_id: str, ctx: RunContext) -> dict:
    """Capture wired node input payloads (`{node_id}_input*`) for run history."""
    prefix = f"{node_id}_"
    payload: dict[str, object] = {}
    for key, value in ctx.values.items():
        if not key.startswith(prefix):
            continue
        local_key = key[len(prefix):]
        if not local_key.startswith("input"):
            continue
        payload[local_key] = _jsonable(value)
    return payload


def _agent_response(node: dict, new_values: dict, ctx: RunContext) -> str | None:
    """Return a concise human-readable response for agent-layer nodes.

    Delegates to the data-driven registry in engine.response_formatters.
    """
    if not _is_agent_node(node.get("type")):
        return None
    from .response_formatters import get_agent_response
    return get_agent_response(node, new_values, ctx)


def _is_agent_node(node_type: object) -> bool:
    if not isinstance(node_type, str):
        return False
    spec = NODE_SPECS.get(node_type)
    return bool(spec and spec.ui.get("palette_group") == "agent")


def _jsonable(v):
    """Best-effort conversion so SSE payload always JSON-serialises."""
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)


def run_workflow_stream(
    dag: dict, alert_payload: dict
) -> Iterator[dict]:
    """
    Execute a workflow and yield an event per phase.

    Event shapes:
      {"type":"workflow_start", "name":..., "total_nodes":N, "order":[ids]}
      {"type":"node_start", "node_id", "node_type", "label", "index", "total", "started_at":<iso>}
      {"type":"node_complete", "node_id", "duration_ms", "status":"ok", "output":{...}}
      {"type":"node_error", "node_id", "duration_ms", "status":"error", "error":"...", "trace":"..."}
      {"type":"workflow_complete", "total_duration_ms", "result":{...}}   # shape matches /run response
      {"type":"workflow_error", "error":"..."}
    """
    from datetime import datetime, timezone
    t0 = time.perf_counter()

    # Allocate the RunContext early so the run_id is known even if
    # topological sort fails — any workflow_error frame below still
    # carries it, so the UI / audit log can correlate.
    ctx = RunContext(alert_payload=alert_payload)

    def _stamp(ev: dict) -> dict:
        """Every frame gets the run_id so a trace can be reconstructed."""
        ev.setdefault("run_id", ctx.run_id)
        return ev

    try:
        nodes_by_id = {n["id"]: n for n in dag["nodes"]}
        edges = dag.get("edges", [])
        order = topological_sort(list(nodes_by_id.values()), edges)
    except Exception as exc:
        yield _stamp({"type": "workflow_error", "error": str(exc)})
        return

    yield _stamp({
        "type": "workflow_start",
        "name": dag.get("name", dag.get("workflow_id", "workflow")),
        "total_nodes": len(order),
        "order": order,
    })

    # Incoming-handler nodes (MCP, excel/csv export, etc.) resolve upstream
    # outputs via build_incoming_outputs() — same as execute_nodes().
    ctx._active_edges = list(edges)
    persisted_node_log: list[dict] = []

    for idx, node_id in enumerate(order, 1):
        node = nodes_by_id[node_id]
        node_type = node["type"]
        label = node.get("label", node_type)
        handler = NODE_HANDLERS.get(node_type)

        # Snapshot so we can describe what the node changed.
        before = {
            "dataset_sigs": {n: (id(df), len(df)) for n, df in ctx.datasets.items()},
            "values": dict(ctx.values),
        }

        started_at = datetime.now(timezone.utc).isoformat()
        yield _stamp({
            "type": "node_start",
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "index": idx,
            "total": len(order),
            "started_at": started_at,
        })

        if not handler:
            yield _stamp({
                "type": "node_error",
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "index": idx,
                "total": len(order),
                "started_at": started_at,
                "duration_ms": 0,
                "status": "error",
                "error": f"Unknown node type '{node_type}'",
                "trace": "",
            })
            persisted_node_log.append({
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "index": idx,
                "total": len(order),
                "status": "error",
                "started_at": started_at,
                "duration_ms": 0,
                "error": f"Unknown node type '{node_type}'",
                "trace": "",
            })
            yield _stamp({"type": "workflow_error", "error": f"Unknown node type '{node_type}' on node '{node_id}'"})
            return

        node_t0 = time.perf_counter()
        node_inputs: dict[str, object] = {}
        try:
            _wire_inputs(node, edges, ctx)
            node_inputs = _snapshot_node_inputs(node_id, ctx)
            input_issues = check_input_port_schema(node, ctx)
            if input_issues:
                raise ValueError(
                    "input contract violated: " + "; ".join(input_issues)
                )
            handler(node, ctx)
            contract_issues = check_output_contract(node, ctx)
            if contract_issues:
                # Surface as a structured node_error so the UI can
                # show a red node immediately; the workflow_error
                # frame below closes the stream. No KeyError surprises
                # for downstream nodes.
                raise ValueError(
                    "output contract violated: " + "; ".join(contract_issues)
                )
        except Exception as exc:
            dur = int((time.perf_counter() - node_t0) * 1000)
            logger.exception("Node %s failed (run_id=%s)", node_id, ctx.run_id)
            err_frame = {
                "type": "node_error",
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "index": idx,
                "total": len(order),
                "started_at": started_at,
                "duration_ms": dur,
                "status": "error",
                "input": node_inputs,
                "error": str(exc),
                "trace": traceback.format_exc(limit=3),
            }
            yield _stamp(err_frame)
            persisted_node_log.append({
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "index": idx,
                "total": len(order),
                "status": "error",
                "started_at": started_at,
                "duration_ms": dur,
                "input": node_inputs,
                "error": str(exc),
                "trace": traceback.format_exc(limit=3),
            })
            yield _stamp({"type": "workflow_error", "error": f"{node_id} ({node_type}): {exc}"})
            return

        dur = int((time.perf_counter() - node_t0) * 1000)
        output_live = _snapshot_output(node, ctx, before, persist=False)
        output_persist = _snapshot_output(node, ctx, before, persist=True)
        yield _stamp({
            "type": "node_complete",
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "index": idx,
            "total": len(order),
            "started_at": started_at,
            "duration_ms": dur,
            "status": "ok",
            "input": node_inputs,
            "output": output_live,
        })
        persisted_node_log.append({
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "index": idx,
            "total": len(order),
            "status": "ok",
            "started_at": started_at,
            "duration_ms": dur,
            "input": node_inputs,
            "output": output_persist,
        })

    total_ms = int((time.perf_counter() - t0) * 1000)
    download_url = None
    if ctx.report_path:
        download_url = f"/report/{Path(ctx.report_path).name}"
    result = {
        "run_id": ctx.run_id,
        "disposition": ctx.disposition,
        "flag_count": ctx.get("flag_count", 0),
        "output_branch": ctx.output_branch,
        "report_path": ctx.report_path,
        "download_url": download_url,
        "datasets": list(ctx.datasets.keys()),
        "sections": {
            name: {"stats": _jsonable(s["stats"]), "narrative": s["narrative"]}
            for name, s in ctx.sections.items()
        },
        "executive_summary": ctx.executive_summary,
        "persisted_run_log": persisted_node_log,
    }
    yield _stamp({
        "type": "workflow_complete",
        "total_duration_ms": total_ms,
        "result": result,
    })


def dry_run_workflow(nodes: list[dict], edges: list[dict]) -> dict:
    """
    In-memory execution for the Copilot self-healing loop (orchestrator-backend parity).

    Runs handlers in topo order and returns per-node outputs in ``outputMap``.
    """
    ctx = RunContext(alert_payload={})
    logs: list[dict] = []
    status = "completed"
    try:
        execute_nodes(nodes, edges, ctx)
    except Exception as exc:
        status = "failed"
        logs.append({
            "nodeId": "",
            "nodeType": "",
            "status": "failed",
            "output": {},
            "error": str(exc),
        })
        return {"status": status, "outputMap": dict(ctx.output_map), "logs": logs}

    for nid, out in ctx.output_map.items():
        node = next((n for n in nodes if n.get("id") == nid), {})
        logs.append({
            "nodeId": nid,
            "nodeType": node.get("type", ""),
            "status": "completed",
            "output": out,
            "error": None,
        })
    return {"status": status, "outputMap": dict(ctx.output_map), "logs": logs}
