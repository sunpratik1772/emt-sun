"""Execute user-provided Starlark on the rows array (hermetic sandbox)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml
from ..starlark_sandbox import StarlarkExecutionError, execute_starlark

_HERE = Path(__file__).parent

logger = logging.getLogger(__name__)


def _upstream_rows(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    code_text = cfg.get("code") or ""
    rows = _upstream_rows(incoming)
    if not code_text.strip():
        return {"rows": rows, "rowCount": len(rows)}

    input_data = {"rows": rows}
    # Also merge all top-level keys from incoming outputs into input_data
    # so that they are directly accessible in Starlark (e.g. input_data["response"]),
    # and also store under the node ID for scoped access.
    for node_id, node_output in incoming.items():
        if isinstance(node_output, dict):
            for k, v in node_output.items():
                if k != "rows":
                    input_data[k] = v
            input_data[node_id] = node_output

    summary = cfg.get("code_summary")
    base: dict[str, Any] = {"rows": rows, "rowCount": len(rows)}
    if isinstance(summary, str) and summary.strip():
        base["code_summary"] = summary.strip()

    try:
        out = execute_starlark(code_text, input_data=input_data, legacy_rows=rows)
    except StarlarkExecutionError as exc:
        logger.exception("code node starlark failed")
        return {**base, "error": str(exc)}
    except Exception as exc:
        logger.exception("code node failed")
        return {**base, "error": str(exc)}

    if not isinstance(out, list):
        out = [out]
    return {**base, "rows": out, "rowCount": len(out)}


NODE_SPEC = _spec_from_yaml(_HERE / "code.yaml", run)
