"""Hermetic Starlark execution for workflow code nodes (no I/O, no imports)."""
from __future__ import annotations

from typing import Any

import starlark as sl


class StarlarkExecutionError(Exception):
    """Raised when user/AI Starlark fails to parse or evaluate."""


def _normalize_output(value: Any) -> list[dict[str, Any]] | list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


_STARLARK_HELPERS = """
def sum(lst):
    val = 0
    for x in lst:
        val += x
    return val

def round(num, ndigits=0):
    factor = 1.0
    for i in range(ndigits):
        factor *= 10.0
    val = float(num) * factor
    if val >= 0:
        val = float(int(val + 0.5))
    else:
        val = float(int(val - 0.5))
    return val / factor
"""


def execute_starlark(
    script: str,
    *,
    input_data: dict[str, Any],
    legacy_rows: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """
    Run a Starlark script in a fresh module.

    Injected globals:
      - ``input_data`` — dict with at least ``rows`` (upstream table).
      - ``rows`` — same list as ``input_data["rows"]`` for older workflows.

    The script should assign ``output`` (preferred) or ``result``.
    If neither is set, returns ``rows`` after execution (mutated in-place).
    """
    text = (script or "").strip()
    if not text:
        rows = list(legacy_rows or input_data.get("rows") or [])
        return rows

    full_script = _STARLARK_HELPERS + "\n" + text
    mod = sl.Module()
    mod["input_data"] = dict(input_data)
    rows = list(legacy_rows if legacy_rows is not None else input_data.get("rows") or [])
    mod["rows"] = rows

    try:
        ast = sl.parse("workflow_code.starlark", full_script)
        sl.eval(mod, ast, sl.Globals.standard())
    except sl.StarlarkError as exc:
        raise StarlarkExecutionError(str(exc)) from exc


    out = mod["output"]
    if out is not None:
        return _normalize_output(out)
    res = mod["result"]
    if res is not None:
        return _normalize_output(res)
    legacy = mod["rows"]
    if legacy is not None and legacy is not rows:
        return _normalize_output(legacy)
    return rows
