"""Shared path helpers for vetted Studio demo workflows."""
from __future__ import annotations

from pathlib import Path


def demo_workflows_dir() -> Path:
    """Canonical location for ``studio_*.json`` demos (``good_examples/``)."""
    backend = Path(__file__).resolve().parents[1]
    good = backend / "good_examples"
    if good.is_dir():
        return good
    return backend / "workflows"


def demo_workflow_path(name: str) -> Path:
    return demo_workflows_dir() / name
