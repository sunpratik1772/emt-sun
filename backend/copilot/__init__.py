"""Copilot package — lazy exports to avoid import cycles with agent.harness."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workflow_generator import WorkflowCopilot as WorkflowCopilot


def __getattr__(name: str):
    if name == "WorkflowCopilot":
        from .workflow_generator import WorkflowCopilot

        return WorkflowCopilot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["WorkflowCopilot"]
