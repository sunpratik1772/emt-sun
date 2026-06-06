"""Validate generated workflows against router improvement_spec."""
from __future__ import annotations

import re
from typing import Any

from engine.node_availability import is_agent_visible_type

_REQUIREMENT_NODE_TYPES: dict[str, frozenset[str]] = {
    "validation": frozenset({"evaluator"}),
    "evaluator": frozenset({"evaluator"}),
    "condition": frozenset({"condition", "router"}),
    "branch": frozenset({"condition", "router"}),
    "outlook": frozenset({"outlook"}),
    "email": frozenset({"outlook", "gmail"}),
}


def improvement_spec_from_metadata(metadata: dict[str, Any] | None) -> list[str]:
    """Normalize required capabilities from router metadata."""
    meta = metadata or {}
    spec = meta.get("improvement_spec")
    if isinstance(spec, dict):
        requires = spec.get("requires")
        if isinstance(requires, list):
            return [str(r).strip().lower() for r in requires if str(r).strip()]
    requires_raw = meta.get("requires")
    if isinstance(requires_raw, list):
        return [str(r).strip().lower() for r in requires_raw if str(r).strip()]
    out: list[str] = []
    if meta.get("wants_validation"):
        out.append("validation")
    if meta.get("wants_outlook"):
        out.append("outlook")
    return out


def validate_improvement_spec(
    workflow: dict[str, Any],
    requirements: list[str],
) -> list[str]:
    """Return human-readable unmet requirements (empty if satisfied)."""
    if not requirements:
        return []
    node_types = {
        str(n.get("type") or "").lower()
        for n in (workflow.get("nodes") or [])
        if isinstance(n, dict)
    }
    missing: list[str] = []
    for req in requirements:
        allowed = _REQUIREMENT_NODE_TYPES.get(req)
        if not allowed:
            continue
        if not (node_types & allowed):
            missing.append(req)
    if "branch" in requirements or "condition" in requirements:
        if not _has_condition_branches(workflow):
            if "branch" not in missing and "condition" not in missing:
                missing.append("branch")
    return missing


def _has_condition_branches(workflow: dict[str, Any]) -> bool:
    nodes_by_id = {
        str(n.get("id")): n
        for n in (workflow.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }
    for edge in workflow.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or edge.get("source") or "")
        handle = str(edge.get("sourceHandle") or edge.get("from_port") or "").lower()
        node = nodes_by_id.get(src) or {}
        if str(node.get("type") or "").lower() == "condition" and handle in {"true", "false"}:
            return True
    return False


def format_improvement_gaps(gaps: list[str]) -> str:
    if not gaps:
        return ""
    items = ", ".join(sorted(set(gaps)))
    return f"Improvement spec not satisfied — missing: {items}."


def canvas_node_types(workflow: dict[str, Any] | None) -> set[str]:
    if not workflow:
        return set()
    return {
        str(n.get("type") or "").lower()
        for n in (workflow.get("nodes") or [])
        if isinstance(n, dict)
    }


def align_improvement_requirements_with_canvas(
    workflow: dict[str, Any] | None,
    requirements: list[str],
) -> list[str]:
    """Drop spec items for integrations the user already removed on the canvas."""
    types = canvas_node_types(workflow)
    out = list(requirements)
    if "outlook" in out and "outlook" not in types:
        out = [r for r in out if r != "outlook"]
    return out


def infer_requirements_from_scenario(scenario: str, *, editing_mode: bool) -> list[str]:
    """Infer improvement requirements from user text when router metadata absent."""
    if not editing_mode:
        return []
    lower = (scenario or "").lower()
    reqs: list[str] = []
    if "validation" in lower or "evaluator" in lower:
        reqs.append("validation")
    if any(k in lower for k in ("branch", "condition", "failures", "failure path")):
        reqs.append("branch")
    if re.search(
        r"\b(outlook|email).{0,40}\b(not avail|not available|unavailable|remove|delete|without)\b",
        lower,
    ) or re.search(
        r"\b(remove|delete|without|no)\s+outlook\b",
        lower,
    ):
        return [r for r in reqs if r != "outlook"]
    if is_agent_visible_type("outlook") and (
        "outlook" in lower or ("email" in lower and "export" not in lower)
    ):
        reqs.append("outlook")
    return reqs


def apply_improvement_acceptance(
    workflow: dict[str, Any] | None,
    validation: dict[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    """Append improvement-spec errors to validation result."""
    if workflow is None or not requirements:
        return validation
    gaps = validate_improvement_spec(workflow, requirements)
    if not gaps:
        return validation
    out = dict(validation)
    errors = list(out.get("errors") or [])
    for gap in gaps:
        errors.append(
            {
                "code": "IMPROVEMENT_SPEC",
                "message": f"Missing required improvement: {gap}",
            }
        )
    out["errors"] = errors
    out["valid"] = False
    return out
