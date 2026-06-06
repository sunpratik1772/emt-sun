"""Tests for Sherpa improvement acceptance and context resolution."""
from __future__ import annotations

from copilot.improvement_acceptance import (
    align_improvement_requirements_with_canvas,
    apply_improvement_acceptance,
    infer_requirements_from_scenario,
    validate_improvement_spec,
)
from copilot.sherpa_context import resolve_workflow_for_edit


def test_infer_requirements_from_improve_prompt() -> None:
    msg = (
        'Improve "Join Comms" with validation, a branch for failures, '
        "and an Outlook summary when the run completes."
    )
    reqs = infer_requirements_from_scenario(msg, editing_mode=True)
    assert "validation" in reqs
    assert "branch" in reqs
    assert "outlook" in reqs


def test_align_requirements_drops_outlook_when_removed_from_canvas() -> None:
    wf = {"nodes": [{"id": "n01", "type": "github"}]}
    reqs = align_improvement_requirements_with_canvas(
        wf,
        ["validation", "branch", "outlook"],
    )
    assert "outlook" not in reqs


def test_validate_improvement_spec_detects_missing_outlook() -> None:
    wf = {
        "nodes": [
            {"id": "n1", "type": "evaluator"},
            {"id": "n2", "type": "condition"},
        ],
        "edges": [
            {"from": "n2", "to": "n3", "sourceHandle": "true"},
            {"from": "n2", "to": "n4", "sourceHandle": "false"},
        ],
    }
    gaps = validate_improvement_spec(wf, ["validation", "branch", "outlook"])
    assert "outlook" in gaps


def test_apply_improvement_acceptance_marks_invalid() -> None:
    wf = {"nodes": [{"id": "n1", "type": "manual_trigger"}], "edges": []}
    validation = {"valid": True, "errors": [], "warnings": []}
    out = apply_improvement_acceptance(wf, validation, ["outlook"])
    assert out["valid"] is False
    assert any(e.get("code") == "IMPROVEMENT_SPEC" for e in out["errors"])


def test_resolve_workflow_for_edit_loads_by_name(monkeypatch) -> None:
    def fake_get(name: str):
        if "Join" in name:
            return {"name": name, "nodes": [{"id": "n1"}], "edges": []}
        return None

    monkeypatch.setattr("copilot.sherpa_context.get_workflow_by_name_db", fake_get)
    wf, err = resolve_workflow_for_edit(
        {"edit_existing_workflow": True, "workflow_name": "Join Comms"},
        canvas_workflow=None,
    )
    assert err is None
    assert wf is not None
    assert wf["nodes"]
