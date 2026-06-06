"""Tests for run-output question detection."""
from __future__ import annotations

from copilot.run_output_questions import is_run_output_question


def test_detects_review_and_reliability_phrases() -> None:
    assert is_run_output_question(
        'Review the latest run of "Join Comms" and suggest one change to improve reliability.'
    )
    assert is_run_output_question("what was the output of it?")
    assert is_run_output_question("describe the output a bit")
    assert is_run_output_question("name top 3 traders from output")


def test_rejects_build_commands() -> None:
    assert not is_run_output_question("build a workflow that analyzes output")
    assert not is_run_output_question("fix the join node")


def test_rejects_empty() -> None:
    assert not is_run_output_question("")
    assert not is_run_output_question("   ")
