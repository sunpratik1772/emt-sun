from __future__ import annotations

from generation.repair.auto_fixer import AutoFixer
from generation.validator_adapter import ValidatorAdapter
from copilot.preflight import preflight_dag


def test_harness_validator_catches_missing_condition_handles() -> None:
    wf = {
        "name": "Pass/Fail Exports",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n02", "type": "csv_extract", "label": "Load", "config": {"source": "leads.csv"}},
            {"id": "n03", "type": "condition", "label": "Gate", "config": {"expression": "row.score >= 80"}},
            {"id": "n04", "type": "csv_output", "label": "Pass", "config": {"filename": "pass.csv"},
             "position": {"y": 100}},
            {"id": "n05", "type": "csv_output", "label": "Fail", "config": {"filename": "fail.csv"},
             "position": {"y": 300}},
        ],
        "edges": [
            {"from": "n01", "to": "n02"},
            {"from": "n02", "to": "n03"},
            {"from": "n03", "to": "n04"},
            {"from": "n03", "to": "n05"},
        ],
    }
    result = ValidatorAdapter().validate(wf)
    assert result["valid"] is False
    assert any("sourceHandle" in (e.get("message") or "") for e in result["errors"])


def test_preflight_repairs_then_passes_validation() -> None:
    wf = {
        "name": "Pass/Fail Exports",
        "nodes": [
            {"id": "n01", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n03", "type": "condition", "label": "Gate", "config": {"expression": "row.score >= 80"},
             "position": {"y": 200}},
            {"id": "n04", "type": "csv_output", "label": "Pass", "config": {"filename": "pass.csv"},
             "position": {"y": 100}},
            {"id": "n05", "type": "csv_output", "label": "Fail", "config": {"filename": "fail.csv"},
             "position": {"y": 300}},
        ],
        "edges": [
            {"from": "n01", "to": "n03"},
            {"from": "n03", "to": "n04"},
            {"from": "n03", "to": "n05"},
        ],
    }
    repaired, validation = preflight_dag(wf)
    assert validation.valid
    handles = {e["to"]: e.get("sourceHandle") for e in repaired["edges"] if e["from"] == "n03"}
    assert handles["n04"] == "true"
    assert handles["n05"] == "false"


def test_auto_fixer_then_validator_adapter_clears_branch_error() -> None:
    wf = {
        "nodes": [
            {"id": "c1", "type": "condition", "config": {"expression": "row.ok"}},
            {"id": "n2", "type": "csv_output", "config": {"filename": "a.csv"}, "position": {"y": 50}},
            {"id": "n3", "type": "csv_output", "config": {"filename": "b.csv"}, "position": {"y": 250}},
        ],
        "edges": [
            {"from": "c1", "to": "n2"},
            {"from": "c1", "to": "n3"},
        ],
    }
    first = ValidatorAdapter().validate(wf)
    assert first["valid"] is False
    AutoFixer().fix(wf, first["errors"])
    second = ValidatorAdapter().validate(wf)
    assert not any("sourceHandle" in (e.get("message") or "") for e in second["errors"])
