"""
Bridge orchestrator-backend node handlers (node, ctx, incoming) -> dbSherpa dag_runner.

Handlers copied from https://github.com/sunpratik1772/orchestrator-backend return
per-node output dicts and read upstream outputs via *incoming*. The legacy
dbSherpa runner calls ``handler(node, ctx)`` and uses pandas datasets on
RunContext — this module adapts between the two models.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

import pandas as pd

from .context import RunContext

logger = logging.getLogger(__name__)

IncomingHandler = Callable[[dict, RunContext, dict[str, Any]], Any]


def build_incoming_outputs(
    node_id: str,
    edges: list[dict],
    output_map: dict[str, Any],
) -> dict[str, Any]:
    """Map upstream node id -> that node's output dict (branch-aware)."""
    incoming: dict[str, Any] = {}
    for e in edges:
        if e.get("target") != node_id and e.get("to") != node_id:
            continue
        src = e.get("source") or e.get("from")
        if src is None or src not in output_map:
            continue
        upstream = output_map[src]
        handle = e.get("sourceHandle")
        if handle and isinstance(upstream, dict) and upstream.get("_type") == "condition":
            rows_key = "rows_true" if handle == "true" else "rows_false"
            incoming[src] = {
                "rows": upstream.get(rows_key, []),
                "rowCount": len(upstream.get(rows_key, [])),
            }
        else:
            incoming[src] = upstream
    return incoming


def _edge_endpoints(edge: dict) -> tuple[str | None, str | None]:
    return edge.get("source") or edge.get("from"), edge.get("target") or edge.get("to")


def apply_output_to_ctx(node: dict, output: Any, ctx: RunContext) -> None:
    """Merge orchestrator-style output dict into RunContext shelves."""
    if not isinstance(output, dict):
        return
    node_id = node.get("id", "node")
    cfg = node.get("config") or {}
    dataset_name = (
        cfg.get("output_name")
        or cfg.get("dataset")
        or cfg.get("table")
        or f"{node_id}_output"
    )
    rows = output.get("rows")
    if isinstance(rows, list):
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        ctx.datasets[str(dataset_name)] = df
        ctx.datasets["rows"] = df
    for key, val in output.items():
        if isinstance(val, str):
            ctx.values[key] = val
    ctx.set(f"{node_id}_output", output)
    if output.get("report_path"):
        ctx.report_path = str(output["report_path"])
    if output.get("disposition"):
        ctx.disposition = str(output["disposition"])


def wrap_incoming_handler(handler: IncomingHandler) -> Callable[[dict, RunContext], None]:
    """Adapt (node, ctx, incoming) -> dict handlers to (node, ctx) runner contract."""

    def sheep_handler(node: dict, ctx: RunContext) -> None:
        edges: list[dict] = getattr(ctx, "_active_edges", None) or []
        incoming = build_incoming_outputs(node["id"], edges, ctx.output_map)
        if inspect.iscoroutinefunction(handler):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, handler(node, ctx, incoming))
                    output = future.result()
            else:
                output = asyncio.run(handler(node, ctx, incoming))
        else:
            output = handler(node, ctx, incoming)
        ctx.output_map[node["id"]] = output
        apply_output_to_ctx(node, output, ctx)

    return sheep_handler


def is_incoming_handler(handler: Callable[..., Any]) -> bool:
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return False
    params = list(sig.parameters.values())
    if len(params) >= 3:
        return params[2].name == "incoming"
    return False
