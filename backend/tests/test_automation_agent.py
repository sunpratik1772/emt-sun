"""Tests for copilot automation orchestration helpers."""
from __future__ import annotations

from copilot.automation_agent import should_build_workflow_first


def test_existing_workflow_automation_skips_build():
    wf = {"name": "Demo", "nodes": [{"id": "n01"}]}
    assert not should_build_workflow_first(
        "Create an automation of the workflow that you just created and run at 9:30 AM",
        wf,
    )


def test_greenfield_pipeline_builds_first():
    assert should_build_workflow_first(
        "Create a workflow which will take alerts from db and write to confluence",
        None,
    )
