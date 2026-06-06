"""Validate a workflow and apply one deterministic repair pass before run."""
from __future__ import annotations

import copy

from generation.repair.auto_fixer import AutoFixer
from engine.bindings import compile_workflow_bindings
from engine.copilot_validate import validate_dag_for_api
from engine.validator import ValidationResult


def preflight_dag(dag: dict) -> tuple[dict, ValidationResult]:
    """Compile bindings, validate, then retry once with AutoFixer when validation fails."""
    dag, _compile_notes = compile_workflow_bindings(dag)
    validation = validate_dag_for_api(dag)
    if validation.valid:
        return dag, validation

    candidate = copy.deepcopy(dag)
    report = AutoFixer().fix(candidate, validation.to_json()["errors"])
    if not report.changed:
        return dag, validation

    candidate, _ = compile_workflow_bindings(candidate)
    repaired_validation = validate_dag_for_api(candidate)
    return candidate, repaired_validation
