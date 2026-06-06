from __future__ import annotations

from engine.context import RunContext
from engine.nodes.code import run as run_code


def _run(code: str, rows: list[dict], **cfg_extra: object) -> dict:
    node = {"id": "c1", "config": {"code": code, **cfg_extra}}
    incoming = {"upstream": {"rows": rows}}
    return run_code(node, RunContext(), incoming)


def test_code_starlark_output_via_input_data() -> None:
    rows = [{"a": 1}, {"a": 2}, {"a": 3}]
    out = _run(
        'output = [{"doubled": r["a"] * 2} for r in input_data["rows"]]',
        rows,
    )
    assert out["rowCount"] == 3
    assert out["rows"] == [{"doubled": 2}, {"doubled": 4}, {"doubled": 6}]


def test_code_starlark_legacy_result_and_rows() -> None:
    rows = [{"company": {"name": "Acme"}, "address": {"city": "NYC"}}]
    out = _run(
        "result = [{'company': r.get('company', {}).get('name', ''), "
        "'city': r.get('address', {}).get('city', '')} for r in rows[:5]]",
        rows,
    )
    assert out["rows"] == [{"company": "Acme", "city": "NYC"}]


def test_code_starlark_rejects_import() -> None:
    out = _run('import os\noutput = []', [{"x": 1}])
    assert "error" in out
    assert out["rows"] == [{"x": 1}]


def test_code_summary_passes_through() -> None:
    out = _run(
        "output = rows",
        [{"x": 1}],
        code_summary="Keeps every row unchanged for the next step.",
    )
    assert out.get("code_summary") == "Keeps every row unchanged for the next step."
