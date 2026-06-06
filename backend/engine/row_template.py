"""Row-level string templates for agent and integration nodes.

Supports both ``{{company}}`` and ``{{row.company}}`` — Copilot often emits
the latter (MCP-style) even on agent nodes.
"""
from __future__ import annotations

import re
from typing import Any

_ROW_FIELD_RE = re.compile(r"\{\{\s*row\.(\w+)\s*\}\}")
_FLAT_FIELD_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def interpolate_row_template(template: str, row: dict[str, Any]) -> str:
    """Substitute row fields into a template string."""
    if not template:
        return template

    def _row_field_repl(match: re.Match[str]) -> str:
        return str(row.get(match.group(1), ""))

    text = _ROW_FIELD_RE.sub(_row_field_repl, template)

    def _flat_field_repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key == "row":
            return match.group(0)
        return str(row.get(key, ""))

    return _FLAT_FIELD_RE.sub(_flat_field_repl, text)


def contains_row_dot_placeholders(text: str) -> bool:
    return bool(_ROW_FIELD_RE.search(text or ""))


def normalize_row_dot_placeholders(text: str) -> str:
    """Rewrite ``{{row.field}}`` → ``{{field}}`` for canonical agent config."""
    return _ROW_FIELD_RE.sub(r"{{\1}}", text or "")
