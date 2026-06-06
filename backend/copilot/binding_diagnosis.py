"""Contract-aware binding diagnosis for Sherpa ask mode and run summaries."""
from __future__ import annotations

import json
import re
from typing import Any

from engine.bindings import UNRESOLVED_PLACEHOLDER_RE, scan_rows_for_unresolved
from engine.mcp_contracts import get_mcp_tool_contract
from engine.mcp_nodes import is_mcp_node_type

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_blob(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = _FENCED_JSON.search(raw)
    if match:
        try:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(raw[start : i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except Exception:
                    return None
    return None


def _rows_from_debug_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("node_output", "n08_output", "rows"):
        block = payload.get(key)
        if isinstance(block, dict) and isinstance(block.get("rows"), list):
            return [r for r in block["rows"] if isinstance(r, dict)]
        if isinstance(block, list):
            return [r for r in block if isinstance(r, dict)]
    datasets = payload.get("datasets") or {}
    if isinstance(datasets, dict):
        for info in datasets.values():
            if isinstance(info, dict) and isinstance(info.get("sample"), list):
                return [r for r in info["sample"] if isinstance(r, dict)]
    return []


def _find_agent_nodes(workflow: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not workflow:
        return []
    return [
        n for n in (workflow.get("nodes") or [])
        if isinstance(n, dict) and n.get("type") == "agent"
    ]


def _find_mcp_nodes(workflow: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not workflow:
        return []
    return [
        n for n in (workflow.get("nodes") or [])
        if isinstance(n, dict) and is_mcp_node_type(n.get("type"))
    ]


def diagnose_binding_issues(
    *,
    user_message: str = "",
    workflow: dict[str, Any] | None = None,
    debug_payload: dict[str, Any] | None = None,
    run_log: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Return structured binding issues with fix hints."""
    issues: list[dict[str, str]] = []
    payload = debug_payload
    if payload is None and user_message.strip().startswith("{"):
        payload = _extract_json_blob(user_message)

    rows: list[dict[str, Any]] = []
    if payload:
        rows = _rows_from_debug_payload(payload)
    elif run_log:
        for entry in run_log:
            output = entry.get("output") or {}
            if isinstance(output, dict):
                node_out = output.get("node_output") or {}
                if isinstance(node_out, dict) and isinstance(node_out.get("rows"), list):
                    rows.extend(r for r in node_out["rows"] if isinstance(r, dict))

    for msg in scan_rows_for_unresolved(rows):
        issues.append({
            "code": "UNRESOLVED_PLACEHOLDER",
            "message": msg,
            "fix": (
                "Agent per-row nodes need `perRow: true` and `rowTemplate` with "
                "`{{company}}` placeholders (engine renders both `{{company}}` and "
                "`{{row.company}}`). If output still shows `{{...}}`, the template "
                "was not interpolated before the LLM ran."
            ),
        })

    for agent in _find_agent_nodes(workflow):
        cfg = agent.get("config") or {}
        node_id = agent.get("id") or "agent"
        if cfg.get("perRow"):
            template = str(cfg.get("rowTemplate") or "")
            if "{{" in template and not template.strip():
                issues.append({
                    "code": "AGENT_MISSING_ROW_TEMPLATE",
                    "message": f"Node {node_id}: perRow is on but rowTemplate is empty.",
                    "fix": "Set rowTemplate to e.g. '{{company}} in {{region}} scored {{score}}'.",
                })
        elif any(
            isinstance(cfg.get(k), str) and UNRESOLVED_PLACEHOLDER_RE.search(str(cfg.get(k)))
            for k in ("prompt", "task")
        ):
            issues.append({
                "code": "AGENT_AGGREGATE_WITH_ROW_TEMPLATE",
                "message": f"Node {node_id}: row placeholders in prompt/task but perRow is false.",
                "fix": "Set perRow: true, outputColumn, maxRows, and rowTemplate for per-row enrichment.",
            })

    for mcp in _find_mcp_nodes(workflow):
        cfg = mcp.get("config") or {}
        node_id = mcp.get("id") or "mcp"
        tool = str(cfg.get("tool") or "")
        contract = get_mcp_tool_contract(tool)
        params = cfg.get("params") or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        if not isinstance(params, dict):
            continue

        if any(
            isinstance(v, str) and UNRESOLVED_PLACEHOLDER_RE.search(v)
            for v in params.values()
        ):
            issues.append({
                "code": "MCP_PARAM_TEMPLATE",
                "message": f"Node {node_id}: MCP params use row templates (tool={tool}).",
                "fix": (
                    "MCP now renders `{{row.field}}` / `{{field}}` into each upstream row "
                    "before calling the bridge. Use summary/description or aliases "
                    "(poem→description, company→summary)."
                ),
            })

        if contract and rows:
            sample = rows[0]
            for req in contract.required_row_fields:
                alias_sources = [k for k, v in contract.aliases.items() if v == req]
                has_field = req in sample and str(sample.get(req) or "").strip()
                has_alias = any(
                    k in sample and str(sample.get(k) or "").strip() for k in alias_sources
                )
                if not has_field and not has_alias:
                    issues.append({
                        "code": "MCP_MISSING_ROW_FIELD",
                        "message": (
                            f"Node {node_id} tool `{tool}` expects row field `{req}` "
                            f"(aliases: {alias_sources or 'none'})."
                        ),
                        "fix": (
                            f"Add a map_transform renaming upstream columns, or set MCP params "
                            f"summary/description with templates, e.g. description: '{{{{row.poem}}}}'."
                        ),
                    })

    # De-dupe by message
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in issues:
        key = item.get("message") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def format_binding_diagnosis_markdown(issues: list[dict[str, str]]) -> str:
    if not issues:
        return ""
    lines = ["**Binding diagnosis**", ""]
    for item in issues[:8]:
        lines.append(f"- **{item.get('code', 'ISSUE')}**: {item.get('message', '')}")
        fix = item.get("fix")
        if fix:
            lines.append(f"  - Fix: {fix}")
    return "\n".join(lines)
