"""Question-aware build narration for Sherpa timeline + design summary."""
from __future__ import annotations

import re
from typing import Any

from copilot.workflow_blueprints import LEADS_HIGH_RISK_EXPRESSION
from engine.node_availability import is_agent_visible_type

_SPLIT_RE = re.compile(r"\s*,\s*|\s+and\s+", re.IGNORECASE)


def _snip(text: str, limit: int = 72) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def build_thinking_monologue(
    scenario: str,
    intent: Any,
    blueprint: Any | None = None,
    *,
    adapter: Any | None = None,
    current_workflow: dict[str, Any] | None = None,
) -> str:
    """LLM thinking monologue for build harness."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_build(
        scenario,
        intent,
        blueprint,
        current_workflow=current_workflow,
    )
    return generate_thinking_monologue(ctx, adapter=adapter)


def build_contextual_plan_steps(
    scenario: str,
    intent: Any,
    blueprint: Any | None = None,
    *,
    adapter: Any | None = None,
) -> list[dict[str, str]]:
    """Legacy hook — single thinking step payload for the harness."""
    monologue = build_thinking_monologue(scenario, intent, blueprint, adapter=adapter)
    return [
        {
            "label": "Thinking",
            "anchor": _snip(scenario, 80),
            "running": monologue,
            "done": monologue,
        }
    ]


def split_request_phrases(scenario: str) -> list[str]:
    """Split a user build prompt into scannable phrase chunks."""
    raw = (scenario or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in _SPLIT_RE.split(raw) if p.strip()]
    return parts or [raw]


def contextual_understanding_detail(scenario: str, intent: Any) -> str:
    phrases = split_request_phrases(scenario)
    if phrases:
        return " · ".join(_snip(p, 56) for p in phrases[:4])
    datasets = ", ".join(getattr(intent, "datasets", ()) or ()) or "general build"
    return f"Building workflow using {datasets}"


def _find_node(compact: dict[str, Any], node_type: str) -> dict[str, Any] | None:
    for node in compact.get("nodes") or []:
        if str(node.get("type") or "") == node_type:
            return node
    return None


def _pipeline_segment(node: dict[str, Any]) -> str:
    cfg = node.get("config") or {}
    ntype = str(node.get("type") or "")
    if ntype in ("csv_extract", "db_query"):
        return str(cfg.get("source") or node.get("label") or "data")
    if ntype == "filter":
        expr = str(cfg.get("expression") or "")
        if "score" in expr and ">=" in expr:
            m = re.search(r">=\s*(\d+)", expr)
            if m:
                return f"score ≥ {m.group(1)}"
        if expr:
            return expr.replace("row.", "")
        return "filter"
    if ntype == "sort":
        key = cfg.get("sortBy") or "column"
        order = cfg.get("order") or "asc"
        return f"sort {key} {order}"
    if ntype == "join":
        return f"join on {cfg.get('leftKey') or 'key'}"
    if ntype == "csv_output":
        return str(cfg.get("filename") or "output.csv")
    if ntype == "excel_output":
        return str(cfg.get("filename") or "output.xlsx")
    if ntype == "outlook":
        return "Outlook alert"
    return str(node.get("label") or ntype)


def design_summary_intro(user_request: str, compact: dict[str, Any]) -> str:
    """Two-sentence plain-language explanation of what the workflow does."""
    name = str(compact.get("name") or "This workflow").strip()
    lower = (user_request or "").lower()
    nodes = compact.get("nodes") or []
    has_filter = any(isinstance(n, dict) and n.get("type") == "filter" for n in nodes)
    has_sort = any(isinstance(n, dict) and n.get("type") == "sort" for n in nodes)
    has_export = any(
        isinstance(n, dict) and n.get("type") in ("csv_output", "excel_output")
        for n in nodes
    )

    lead = f"I built **{name}** to turn your request into a runnable pipeline on the canvas."
    if has_filter and ("high-risk" in lower or "high risk" in lower):
        tail = (
            "It loads your dataset, keeps rows that match the high-risk rule we discussed, "
            "and writes the result to an export file you can open or schedule."
        )
    elif has_filter:
        tail = (
            "It loads your data, applies the filter you asked for, "
            "and passes the matching rows to the export step."
        )
    elif has_sort and has_export:
        tail = (
            "It loads the source file, ranks the rows the way you specified, "
            "and saves the sorted result to an export file."
        )
    elif has_export:
        tail = "It loads the source data and writes a clean export file at the end."
    else:
        tail = "Each step runs in order so you can run it once and inspect the output."

    return f"{lead} {tail}"


def pipeline_display_line(compact: dict[str, Any]) -> str:
    """Claude-style arrow chain for the chat reply."""
    skip = {"manual_trigger", "schedule", "api_trigger", "webhook_trigger", "note"}
    segments = [
        _pipeline_segment(n)
        for n in (compact.get("nodes") or [])
        if str(n.get("type") or "") not in skip
    ]
    if not segments:
        return ""
    return " → ".join(f"`{seg}`" for seg in segments)


def assumption_close_line(user_request: str, compact: dict[str, Any]) -> str:
    """One collaborative closing sentence when Sherpa made an interpretation."""
    req = (user_request or "").strip()
    lower = req.lower()
    filter_node = _find_node(compact, "filter")
    if filter_node and ("high-risk" in lower or "high risk" in lower):
        expr = (filter_node.get("config") or {}).get("expression") or ""
        if "score" in str(expr) and (">=" in str(expr) or ">" in str(expr)):
            human = _human_filter_expression(str(expr))
            return f'I used {human} for "high-risk." Tell me if you meant a different rule.'
    if filter_node and "filter" in lower:
        expr = (filter_node.get("config") or {}).get("expression") or ""
        if expr:
            return "I picked that filter from your prompt — tell me if you want a different rule."
    return ""


def build_run_review_monologue(
    user_message: str,
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    *,
    route_metadata: dict[str, Any] | None = None,
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue while Sherpa reviews a completed workflow run."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_explain_run(
        user_message,
        workflow,
        run_log,
        route_metadata=route_metadata,
    )
    return generate_thinking_monologue(ctx, adapter=adapter)


_SKIP_NODE_TYPES = frozenset({
    "manual_trigger", "schedule", "api_trigger", "webhook_trigger", "note",
})

_FRIENDLY_NODE_TYPES: dict[str, str] = {
    "csv_extract": "CSV Extract",
    "db_query": "Database Query",
    "filter": "Filter",
    "sort": "Sort",
    "join": "Join",
    "aggregate": "Aggregate",
    "group_by": "Group By",
    "csv_output": "CSV Export",
    "excel_output": "Excel Export",
    "jira_mcp": "Jira MCP",
    "confluence_mcp": "Confluence MCP",
    "github_mcp": "GitHub MCP",
    "mcp": "MCP Tool",
    "condition": "Condition",
    "router": "Router",
    "map_transform": "Map / Transform",
}


def _friendly_node_type(ntype: str) -> str:
    key = (ntype or "").strip().lower()
    if key in _FRIENDLY_NODE_TYPES:
        return _FRIENDLY_NODE_TYPES[key]
    return key.replace("_", " ").title() if key else "Step"


def _action_nodes(compact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        n for n in (compact.get("nodes") or [])
        if isinstance(n, dict) and str(n.get("type") or "") not in _SKIP_NODE_TYPES
    ]


def _extract_score_threshold(expression: str) -> str | None:
    expr = (expression or "").strip()
    for pattern in (r">=\s*(\d+(?:\.\d+)?)", r">\s*(\d+(?:\.\d+)?)", r"<=\s*(\d+(?:\.\d+)?)", r"<\s*(\d+(?:\.\d+)?)"):
        m = re.search(pattern, expr)
        if m and "score" in expr.lower():
            op = ">=" if ">=" in pattern else ">" if ">" in pattern else "<=" if "<=" in pattern else "<"
            return f"score {op} {m.group(1)}"
    return None


def _human_filter_expression(expression: str) -> str:
    expr = (expression or "").strip()
    if not expr:
        return "matching rows"
    threshold = _extract_score_threshold(expr)
    if threshold:
        return threshold
    return expr.replace("row.", "")


def _explain_filter_why(user_request: str, expression: str) -> str:
    lower = (user_request or "").lower()
    expr = (expression or "").strip()
    if "high-risk" in lower or "high risk" in lower:
        human = _human_filter_expression(expr)
        return (
            f'You asked for high-risk rows — I used a **Filter** with `{expr}` '
            f"({human}) because that phrase is not a column on its own."
        )
    if "filter" in lower or "where" in lower:
        return f"You asked to filter the data, so I used `{expr}` to keep only matching rows."
    return f"I added this filter with `{expr}` to narrow rows before the next step."


def explain_node_line(node: dict[str, Any], user_request: str) -> str:
    """One sentence: node type, values, and why (earlier Sherpa walkthrough style)."""
    cfg = node.get("config") or {}
    ntype = str(node.get("type") or "")
    label = str(node.get("label") or node.get("id") or "Step").strip()
    friendly = _friendly_node_type(ntype)

    if ntype == "csv_extract":
        source = cfg.get("source") or "your CSV file"
        return (
            f"**{label}** — I used **{friendly}** to load `{source}` "
            f"because your prompt starts from that file."
        )
    if ntype == "db_query":
        source = cfg.get("source") or cfg.get("table") or "the database table"
        return (
            f"**{label}** — I used **{friendly}** on `{source}` "
            f"to pull the rows this pipeline needs."
        )
    if ntype == "filter":
        expr = str(cfg.get("expression") or "").strip()
        why = _explain_filter_why(user_request, expr)
        return f"**{label}** — {why}"
    if ntype == "sort":
        key = cfg.get("sortBy") or "column"
        order = str(cfg.get("order") or "asc").lower()
        direction = "highest first" if order.startswith("desc") else "lowest first"
        return (
            f"**{label}** — I used **{friendly}** on `{key}` ({order}) "
            f"so the export lists {direction}, as you requested."
        )
    if ntype == "join":
        lk = cfg.get("leftKey") or "left key"
        rk = cfg.get("rightKey") or lk
        jt = str(cfg.get("joinType") or "inner").lower()
        return (
            f"**{label}** — I used **{friendly}** ({jt}) on `{lk}` = `{rk}` "
            f"to combine the two datasets you named."
        )
    if ntype in ("aggregate", "group_by"):
        by_col = cfg.get("groupBy") or cfg.get("group_by") or "group key"
        metric = cfg.get("metric") or cfg.get("aggregate") or "totals"
        return (
            f"**{label}** — I used **{friendly}** grouped by `{by_col}` "
            f"to compute {metric} before ranking or export."
        )
    if ntype == "csv_output":
        fn = cfg.get("filename") or "output.csv"
        return (
            f"**{label}** — I used **CSV Export** to write `{fn}` "
            f"as the CSV summary you asked for."
        )
    if ntype == "excel_output":
        fn = cfg.get("filename") or "output.xlsx"
        return (
            f"**{label}** — I used **Excel Export** to write `{fn}` "
            f"as the Excel report you asked for."
        )
    if ntype in ("jira_mcp", "confluence_mcp", "github_mcp", "mcp"):
        tool = cfg.get("tool") or "bridge tool"
        return (
            f"**{label}** — I used **{friendly}** with `{tool}` "
            f"to call the integration bridge on upstream rows."
        )
    if ntype == "outlook":
        to_addr = cfg.get("to") or cfg.get("recipient") or "the configured recipient"
        return (
            f"**{label}** — I used **Outlook** to email `{to_addr}` "
            f"when the run completes."
        )
    return f"**{label}** — I used **{friendly}** here to carry the pipeline forward."


def design_node_walkthrough_lines(user_request: str, compact: dict[str, Any]) -> list[str]:
    """Numbered per-node explanations: which node, which values, and why."""
    nodes = _action_nodes(compact)
    if not nodes:
        return []
    return [
        f"{idx}. {explain_node_line(node, user_request)}"
        for idx, node in enumerate(nodes, 1)
    ]


def design_rationale_lines(user_request: str, compact: dict[str, Any]) -> list[str]:
    """Per-node walkthrough for design replies."""
    return design_node_walkthrough_lines(user_request, compact)


def build_ask_thinking_monologue(
    user_message: str,
    *,
    workflow: dict[str, Any] | None = None,
    recent_errors: list[dict[str, Any]] | None = None,
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue while Sherpa answers an advisory question."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_ask(
        user_message,
        workflow=workflow,
        recent_errors=recent_errors,
    )
    return generate_thinking_monologue(ctx, adapter=adapter)


def build_load_thinking_monologue(
    message: str,
    *,
    query: str = "",
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue while Sherpa searches saved workflows."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_load(message, query=query)
    return generate_thinking_monologue(ctx, adapter=adapter)


def build_automate_thinking_monologue(
    message: str,
    *,
    workflow: dict[str, Any] | None = None,
    build_first: bool = False,
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue while Sherpa sets up an automation."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_automate(
        message,
        workflow=workflow,
        build_first=build_first,
    )
    return generate_thinking_monologue(ctx, adapter=adapter)


def build_failure_thinking_monologue(
    user_request: str,
    payload: dict[str, Any],
    *,
    adapter: Any | None = None,
) -> str:
    """LLM thinking monologue while Sherpa diagnoses a failed build."""
    from copilot.thinking_monologue import ThinkingMonologueContext, generate_thinking_monologue

    ctx = ThinkingMonologueContext.for_failure(user_request, payload)
    return generate_thinking_monologue(ctx, adapter=adapter)
