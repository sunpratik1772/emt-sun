"""
Deterministic, LLM-free repairs for validator errors we can fix
mechanically. Runs BEFORE the LLM repair loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from copilot.workflow_finalize import _repair_condition_source_handles
from engine.mcp_nodes import is_mcp_node_type
from engine.validation_codes import ValidationErrorCode


@dataclass
class AutoFixReport:
    applied: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return len(self.applied) > 0


def _find_node(workflow: dict, node_id: str) -> dict | None:
    for n in workflow.get("nodes") or []:
        if isinstance(n, dict) and n.get("id") == node_id:
            return n
    return None


def _fix_missing_label(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    node = _find_node(workflow, error.get("node_id") or "")
    if not node or node.get("label"):
        return False
    t = node.get("type") or "node"
    label = str(t).replace("_", " ").title()
    node["label"] = label
    report.applied.append(f"{node['id']}.label: set to '{label}'")
    return True


def _normalize_edge_schema(workflow: dict) -> bool:
    changed = False
    for edge in workflow.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        if "from" not in edge and "source" in edge:
            edge["from"] = edge.pop("source")
            changed = True
        if "to" not in edge and "target" in edge:
            edge["to"] = edge.pop("target")
            changed = True
    return changed


def _fix_condition_source_handles(workflow: dict, error: dict, report: AutoFixReport) -> bool:
    message = (error.get("message") or "").lower()
    code = error.get("code")
    if code not in (ValidationErrorCode.BAD_EDGE, "BAD_EDGE"):
        return False
    if "sourcehandle" not in message:
        return False
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    if not nodes or not edges:
        return False
    before = [
        (e.get("from") or e.get("source"), e.get("to") or e.get("target"), e.get("sourceHandle"))
        for e in edges
        if isinstance(e, dict)
    ]
    _repair_condition_source_handles(nodes, edges)
    after = [
        (e.get("from") or e.get("source"), e.get("to") or e.get("target"), e.get("sourceHandle"))
        for e in edges
        if isinstance(e, dict)
    ]
    if before == after:
        return False
    report.applied.append("condition: set sourceHandle true/false on branch edges")
    return True


def _fix_mcp_param_templates(workflow: dict, report: AutoFixReport) -> bool:
    from engine.bindings import normalize_template_strings_in_value

    changed = False
    for node in workflow.get("nodes") or []:
        if not isinstance(node, dict) or not is_mcp_node_type(node.get("type")):
            continue
        cfg = node.setdefault("config", {})
        if not isinstance(cfg, dict) or cfg.get("params") is None:
            continue
        normalized, item_changed = normalize_template_strings_in_value(cfg["params"])
        if item_changed:
            cfg["params"] = normalized
            node_id = node.get("id") or "mcp"
            report.applied.append(f"{node_id}.config.params: {{row.field}} → {{field}}")
            changed = True
    return changed


def _fix_agent_row_templates(workflow: dict, report: AutoFixReport) -> bool:
    from engine.row_template import contains_row_dot_placeholders, normalize_row_dot_placeholders

    changed = False
    for node in workflow.get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") != "agent":
            continue
        cfg = node.setdefault("config", {})
        if not isinstance(cfg, dict):
            continue
        node_id = node.get("id") or "agent"
        for key in ("prompt", "task", "rowTemplate"):
            value = cfg.get(key)
            if not isinstance(value, str) or not contains_row_dot_placeholders(value):
                continue
            cfg[key] = normalize_row_dot_placeholders(value)
            report.applied.append(f"{node_id}.config.{key}: {{row.field}} → {{field}}")
            changed = True
    return changed


_RULES: dict[ValidationErrorCode, Callable[[dict, dict, AutoFixReport], bool]] = {
    ValidationErrorCode.MISSING_LABEL: _fix_missing_label,
    ValidationErrorCode.BAD_EDGE: _fix_condition_source_handles,
}


class AutoFixer:
    def fix(self, workflow: dict, errors: list[dict]) -> AutoFixReport:
        report = AutoFixReport()
        if not isinstance(workflow, dict):
            return report

        if _normalize_edge_schema(workflow):
            report.applied.append("edges: converted {source,target} → {from,to}")

        if _fix_agent_row_templates(workflow, report):
            pass

        if _fix_mcp_param_templates(workflow, report):
            pass

        for err in errors or []:
            code = err.get("code")
            rule = _RULES.get(code) if code else None
            if not rule:
                continue
            try:
                rule(workflow, err, report)
            except Exception:  # pragma: no cover
                continue
        return report
