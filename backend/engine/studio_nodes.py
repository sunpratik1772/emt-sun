"""
Studio-approved orchestrator node types (palette + agent).

Derived from the live registry — only ``studio_active`` nodes are approved
for Copilot generation and demo validation.
"""
from __future__ import annotations

from typing import Final


def _load_studio_active_types() -> frozenset[str]:
    from engine.registry import all_specs

    return frozenset(s.type_id for s in all_specs())


STUDIO_APPROVED_NODE_TYPES: Final[frozenset[str]] = _load_studio_active_types()
