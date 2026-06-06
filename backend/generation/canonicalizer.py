"""Deterministic workflow canonicalization pass.

This layer runs after draft generation and before final response so the UI
receives a Sherpa-native shape even when the model emitted legacy n8n-style
dialects. It intentionally does NOT try to solve business intent; it only
normalizes execution compatibility.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .repair.auto_fixer import AutoFixer


@dataclass
class CanonicalizationResult:
    workflow: dict[str, Any] | None
    changed: bool
    applied: list[str]


class Canonicalizer:
    """Apply deterministic compatibility rewrites once."""

    def __init__(self, auto_fixer: AutoFixer | None = None) -> None:
        self._auto_fixer = auto_fixer or AutoFixer()

    def canonicalize(self, workflow: dict[str, Any] | None) -> CanonicalizationResult:
        if not isinstance(workflow, dict):
            return CanonicalizationResult(workflow=None, changed=False, applied=[])
        candidate = copy.deepcopy(workflow)
        report = self._auto_fixer.fix(candidate, errors=[])
        return CanonicalizationResult(
            workflow=candidate,
            changed=report.changed,
            applied=list(report.applied),
        )

