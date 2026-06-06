"""
Adapter over `engine.validator.validate_dag`.

This layer exists so the harness depends on a small stable interface
rather than directly on the engine. Swapping in a different validator
(or adding post-validator scoring) becomes a local change here.
"""
from __future__ import annotations

from copilot.orchestrator_validator import validate_workflow as validate_orchestrator
from engine.validation_codes import ValidationErrorCode as VC
from engine.validator import validate_dag


def _orchestrator_error_code(message: str) -> VC:
    if "sourceHandle" in message:
        return VC.BAD_EDGE
    if "no incoming edge" in message:
        return VC.ORPHAN_NODE
    if "unknown type" in message:
        return VC.UNKNOWN_TYPE
    if "missing required config" in message:
        return VC.MISSING_REQUIRED_PARAM
    return VC.BAD_EDGE


class ValidatorAdapter:
    """Stateless wrapper around the deterministic DAG validator."""

    def validate(self, workflow: dict | None) -> dict:
        """Return a `ValidationResult.to_json()` payload.

        When the workflow is `None` (model produced unparseable JSON)
        we return a synthetic failure so the harness can still reason
        about it uniformly.
        """
        if workflow is None:
            return {
                "valid": False,
                "errors": [
                    {
                        "code": "UNPARSEABLE_JSON",
                        "message": (
                            "Model output did not contain a parseable JSON object."
                        ),
                        "severity": "error",
                        "node_id": None,
                        "field": None,
                    }
                ],
                "warnings": [],
                "summary": "unparseable JSON",
            }

        engine_result = validate_dag(workflow)
        orch_err = validate_orchestrator(workflow)
        if orch_err:
            engine_result.add(_orchestrator_error_code(orch_err), orch_err)
        return engine_result.to_json()
