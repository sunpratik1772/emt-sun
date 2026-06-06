"""Tests for engine.row_template — agent row placeholder interpolation."""
from __future__ import annotations

from engine.row_template import (
    contains_row_dot_placeholders,
    interpolate_row_template,
    normalize_row_dot_placeholders,
)


ROW = {
    "company": "Flux Media",
    "region": "MEA",
    "score": 95,
    "stage": "negotiation",
}


def test_interpolate_flat_placeholders() -> None:
    out = interpolate_row_template(
        "{{company}} in {{region}} scored {{score}} at {{stage}}",
        ROW,
    )
    assert out == "Flux Media in MEA scored 95 at negotiation"


def test_interpolate_row_dot_placeholders() -> None:
    out = interpolate_row_template(
        "Company: {{row.company}}, Region: {{row.region}}",
        ROW,
    )
    assert out == "Company: Flux Media, Region: MEA"


def test_interpolate_mixed_placeholder_styles() -> None:
    out = interpolate_row_template("{{company}} / {{row.region}}", ROW)
    assert out == "Flux Media / MEA"


def test_interpolate_missing_field_is_empty() -> None:
    assert interpolate_row_template("{{missing}}", ROW) == ""


def test_normalize_row_dot_placeholders() -> None:
    assert normalize_row_dot_placeholders("{{row.company}}") == "{{company}}"


def test_contains_row_dot_placeholders() -> None:
    assert contains_row_dot_placeholders("{{row.company}}")
    assert not contains_row_dot_placeholders("{{company}}")
