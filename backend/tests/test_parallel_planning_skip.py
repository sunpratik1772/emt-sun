"""Tests for skipping parallel planning on simple linear builds."""
from __future__ import annotations

from generation.harness.intent import classify
from generation.harness.runner import AgentRunner


def test_skip_parallel_planning_for_simple_csv_export() -> None:
    runner = AgentRunner()
    intent = classify(
        "Load leads.csv, filter high-risk rows, and export a CSV summary.",
        known_datasets={"leads.csv"},
    )
    assert runner._should_skip_parallel_planning(intent, None) is True


def test_keep_parallel_planning_for_multi_scenario() -> None:
    runner = AgentRunner()
    intent = classify("Detect spoofing and layering on FX desk with csv output")
    assert runner._should_skip_parallel_planning(intent, None) is False
