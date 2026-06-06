"""
Self-healing workflow generator from orchestrator-backend.

.. deprecated::
   Studio Copilot now uses :class:`agent.harness.runner.AgentRunner`.
   This module remains for reference, benchmarks, and ``finalize_workflow``.

Source: https://github.com/sunpratik1772/orchestrator-backend
      backend/copilot/workflow_generator.py

8-layer pipeline: plan → orchestrator schema validate → semantic dry-run → repair (max N).
Layer 4a uses :mod:`copilot.orchestrator_validator` (orchestrator-backend parity),
not :func:`engine.validator.validate_dag` (Studio /run preflight).
Emits orchestrator-style dict events; :mod:`workflow_generator` translates
those to the Studio SSE phase timeline.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable

from engine.dag_runner import dry_run_workflow
from engine.registry import all_specs, studio_manifest
from engine.validator import _is_entry_node_type

from .orchestrator_validator import validate_workflow as validate_orchestrator_schema
from .workflow_finalize import finalize_workflow, _normalize_workflow_for_validator
from llm import gemini_configured, get_default_adapter

logger = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], None]
MAX_REPAIR_ATTEMPTS_DEFAULT = 2


_DATASET_SCHEMAS = """All datasets are Oracle-backed (connector: oracle). Use db_query with SELECT … FROM <table>.

orders.csv (oracle:DEMO.ORDERS — table `orders`):
  columns: order_id, sku, region, quantity, revenue

products.csv (oracle:DEMO.PRODUCTS — table `products`):
  columns: sku, name, category, unit_price

leads.csv (oracle:DEMO.LEADS — table `leads`):
  columns: lead_id, company, region, score, stage

comms_messages (oracle:SURVEILLANCE.COMMS_MESSAGES):
  columns: message_id, alert_id, participant_id, trader_id, trader_name, book, timestamp,
           keyword, channel, display_post, event_type, relevance_score
  Use LIMIT in SQL for top-N rows, e.g. SELECT * FROM comms_messages LIMIT 20

hs_trades / hs_alerts / hs_orders / hs_exec / market_ticks (oracle:SURVEILLANCE.*):
  Load via db_query; table names match catalog ids (hs_trades, hs_alerts, …).
  hs_alerts columns: alert_id, trader_id, trader_name, keyword, alert_date, scenario, description, …
  Demo scenario values: front_running_positive, front_running_negative (not Layering/Spoofing/Front-Running).
"""

_NODE_CONFIG_EXAMPLES = """Worked examples for the trickier nodes. Field names here MUST match the
<node_field_keys> block above (which is the source of truth).

db_query:
  { "source": "orders.csv", "query": "SELECT * FROM orders" }

filter:
  { "expression": "row.score >= 75" }

map_transform:
  { "mappings": [
      { "to": "revenue", "expression": "row.quantity * row.unit_price" },
      { "from": "old_col", "to": "new_col" }
  ]}

select_columns:
  { "columns": "col1,col2,col3" }

sort:
  { "sortBy": "salary", "order": "asc" }

group_by:
  { "groupBy": "region",
    "aggregateCol": "total",
    "aggregateFn": "sum",
    "alias": "total_revenue" }

join:
  { "leftKey": "product_sku", "rightKey": "sku", "joinType": "inner" }

condition:
  { "expression": "row.status === 'delivered'" }
  Edges from condition MUST set sourceHandle: "true" or "false".

router:
  { "routes": [
    { "label": "electronics", "condition": "row.category === 'Electronics'" },
    { "label": "default", "condition": "true" }
  ]}
  Edges from router MUST set sourceHandle to the route label.

agent (aggregate — one LLM call on all rows):
  { "prompt": "You are an analyst.", "task": "Summarize trends in the dataset" }

agent (per-row enrichment — poem, opener, score; set perRow, rowTemplate, cap rows):
  { "prompt": "Write a short inspiring poem for this sales lead.",
    "task": "Output only the poem text.",
    "perRow": true,
    "rowTemplate": "{{company}} in {{region}} scored {{score}} at stage {{stage}}",
    "outputColumn": "poem",
    "maxRows": 10 }
  Use flat {{field}} placeholders in rowTemplate — not {{row.field}}.

code (Starlark — sandboxed; use def for loops, assign output):
  { "code": "output = [r for r in input_data['rows'] if r.get('active') == True]",
    "code_summary": "Keeps only rows where the active flag is true, so downstream steps see live records only." }
  Globals: input_data, rows, output/result only — never workflow_run_id or run_id.
  Top-N example:
  { "code": "def top_messages(rows):\\n    ranked = sorted(rows, key=lambda r: r.get('relevance_score', 0), reverse=True)\\n    return ranked[:20]\\noutput = top_messages(input_data['rows'])",
    "code_summary": "Sorts chat messages by relevance score and keeps the top 20 for the comms tab." }

evaluator (QA gate — passed rows only):
  { "criteria": "row.alert_id != None and row.trader_id != None", "label": "valid_anomaly" }
  Adds _eval on each row (label or "failed") but forwards ONLY passing rows downstream.
  Do not use _passed; do not count failures in a later code node unless you validate in filter/code instead.

confluence_mcp (publish shaped upstream rows):
  { "tool": "confluence_publish_report", "params": {} }
  Upstream map_transform or code must emit title and body_markdown per row.
  For AI-written reports use agent with emitPublishRow=true then confluence_mcp params: {}.

excel_output (multi-tab — one upstream per tab, wire edges in parallel into excel):
  { "filename": "report.xlsx", "tabNames": "Qualified Leads,Top 20 Comms" }
  tabNames may be a comma-separated string OR a JSON array of strings — both work.
  First upstream rows → first tab name; second upstream → second tab. Use sort/code to shape each tab.

mcp (Atlassian/GitHub bridge — use only these exact working tool names):
  Confluence publish:
  { "integration": "confluence", "tool": "confluence_publish_report",
    "confluenceSpaceKey": "MFS", "pageTitle": "Market Tick Spread Alert Analysis", "params": {} }
  The upstream agent should emit a row with title and body_markdown
  (agent config emitPublishRow=true, pageTitle="...").
  Jira issue:
  { "integration": "jira", "tool": "jira_create_issue",
    "params": { "project": "DEMO", "issue_type": "Task",
      "summary": "Poem for {{row.company}}", "description": "{{row.poem}}" } }
  Upstream rows must include poem/company or use templated params above (bridge reads summary/description).
  Search Confluence:
  { "integration": "confluence", "tool": "confluence_search_pages",
    "params": { "space": "MFS", "limit": 5 } }
  Never use create_confluence_page; it is not a bridge tool. Use confluence_publish_report.
"""


def _node_registry() -> dict[str, str]:
    out: dict[str, str] = {}
    for n in studio_manifest()["nodes"]:
        sid = n.get("palette_group", "general")
        out[n["type_id"]] = f"[{sid}] {n['description']}"
    return out


def _node_field_keys() -> str:
    lines: list[str] = []
    for spec in all_specs():
        if not spec.params:
            lines.append(f"- {spec.type_id}: (no config)")
            continue
        parts = [f"{p.name}{'*' if p.required else ''}" for p in spec.params]
        lines.append(f"- {spec.type_id}: {', '.join(parts)}   (* = required)")
    return "\n".join(lines)


def _system_prompt(
    existing: list[dict],
    history: list[dict],
    message: str,
    corrector_trace: str | None,
) -> str:
    history_str = "\n".join(
        f"{'User' if h.get('role') == 'user' else 'Assistant'}: {h.get('content', '')}"
        for h in history[-8:]
    ) or "No prior conversation"

    corrector_block = (
        f"\n<corrector_traceback>\nCRITICAL: Your previous attempt failed validation. "
        f"Fix the EXACT issue below and regenerate the WHOLE plan.\n{corrector_trace}\n</corrector_traceback>\n"
        if corrector_trace
        else ""
    )

    existing_str = (
        "\n".join(
            f"- \"{w.get('name')}\": {w.get('description') or 'no description'}"
            for w in existing[:15]
        )
        or "None yet"
    )

    return f"""You are the dbSherpa Studio Copilot — an AI workflow architect.
{corrector_block}
<node_registry>
{json.dumps(_node_registry(), indent=2)}
</node_registry>

<node_field_keys>
AUTHORITATIVE config keys per node type:
{_node_field_keys()}
</node_field_keys>

<dataset_schemas>
{_DATASET_SCHEMAS}
</dataset_schemas>

<node_config_examples>
{_NODE_CONFIG_EXAMPLES}
</node_config_examples>

<existing_workflows>
{existing_str}
</existing_workflows>

<conversation_history>
{history_str}
</conversation_history>

<layout_rules>
- Triggers: x = 60
- Data nodes: x = 320 (stacked y = 180, 380, 580 …)
- Transform nodes: x = 600
- Output nodes: x = 900
- Vertical spacing: 200px between siblings
</layout_rules>

<constraints>
1. ONLY use node types EXACTLY as written in <node_registry>.
2. csv_extract config.source must be an exact filename from <dataset_schemas>.
3. Every node must be connected; graph must be acyclic.
4. Use camelCase config keys from <node_field_keys>.
5. condition / router edges MUST set sourceHandle.
6. thinking_steps: 3-6 short phrases.
7. workflow is null only when intent is answer_question.
</constraints>

User message: {message}

Respond ONLY with valid JSON:
{{
  "intent": "create_workflow" | "answer_question",
  "answer": "string",
  "thinking_steps": ["string"],
  "workflow": {{
    "name": "string",
    "description": "string",
    "nodes": [{{ "id": "n1", "type": "manual_trigger", "label": "Start", "config": {{}}, "position": {{ "x": 60, "y": 280 }} }}],
    "edges": [{{ "id": "e1", "source": "n1", "target": "n2", "sourceHandle": "true" }}]
  }} | null
}}"""


_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = _FENCED_JSON.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except Exception:
                    return None
    return None


def _stub_plan() -> str:
    return json.dumps({
        "intent": "create_workflow",
        "answer": "Set GEMINI_API_KEY to enable AI planning. Returning a demo workflow.",
        "thinking_steps": ["Loading stub workflow"],
        "workflow": {
            "name": "Stub Workflow",
            "description": "Demo workflow (no Gemini key configured).",
            "nodes": [
                {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}, "position": {"x": 60, "y": 280}},
                {"id": "n2", "type": "csv_extract", "label": "Load Leads", "config": {"source": "leads.csv"}, "position": {"x": 320, "y": 280}},
                {"id": "n3", "type": "filter", "label": "Hot Leads", "config": {"expression": "row.score >= 80"}, "position": {"x": 600, "y": 280}},
                {"id": "n4", "type": "csv_output", "label": "Output", "config": {"filename": "hot_leads.csv"}, "position": {"x": 900, "y": 280}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
                {"id": "e2", "source": "n2", "target": "n3"},
                {"id": "e3", "source": "n3", "target": "n4"},
            ],
        },
    })


def _generate(prompt: str) -> str:
    if not gemini_configured():
        return _stub_plan()
    try:
        return get_default_adapter().chat_turn(
            system_prompt="You are dbSherpa Studio Copilot.",
            history=[],
            user_turn=prompt,
            temperature=0.1,
            json_mode=True,
        )
    except Exception as exc:
        logger.warning("Gemini planning failed: %s", exc)
        return _stub_plan()


def _validate_schema(workflow: dict) -> str | None:
    """Layer 4a — orchestrator-backend schema check (not Studio validate_dag)."""
    dag = _normalize_workflow_for_validator(workflow)
    return validate_orchestrator_schema(dag)


def _semantic_dry_run(workflow: dict) -> str | None:
    dag = _normalize_workflow_for_validator(workflow)
    nodes = dag["nodes"]
    edges = dag["edges"]
    if not nodes:
        return "Workflow has zero nodes."

    try:
        result = dry_run_workflow(nodes, edges)
    except Exception as exc:
        return f"Dry-run crashed: {exc}"

    logs = result.get("logs") or []
    failed = next((l for l in logs if l.get("status") == "failed"), None)
    if failed:
        return (
            f"Node {failed.get('nodeId')!r} ({failed.get('nodeType')}) failed: {failed.get('error')}"
        )

    output_map = result.get("outputMap") or {}
    has_outgoing = {e.get("from") or e.get("source") for e in edges}
    sinks = [n for n in nodes if n["id"] not in has_outgoing]

    for sink in sinks:
        out = output_map.get(sink["id"])
        if not out:
            continue
        if sink["type"] in {"note"} or str(sink["type"]).endswith("_trigger"):
            continue
        rows = out.get("rows") if isinstance(out, dict) else None
        rows_written = out.get("rowsWritten") if isinstance(out, dict) else None
        row_count = len(rows) if isinstance(rows, list) else rows_written
        if row_count == 0:
            return (
                f"Terminal node {sink['id']!r} ({sink['type']}) produced 0 rows. "
                f"Check filter expressions, joins, or upstream data."
            )

    for n in nodes:
        if n.get("type") != "condition":
            continue
        out = output_map.get(n["id"]) or {}
        t_n = len(out.get("rows_true") or []) if isinstance(out, dict) else 0
        f_n = len(out.get("rows_false") or []) if isinstance(out, dict) else 0
        total = t_n + f_n
        if total > 0 and (t_n == 0 or f_n == 0):
            expr = (n.get("config") or {}).get("expression")
            return (
                f"Condition {n['id']!r} expression {expr!r} routed all {total} rows to one branch "
                f"(true={t_n}, false={f_n})."
            )
    return None


def run_pipeline_sync(
    message: str,
    history: list[dict],
    existing: list[dict],
    emit: EmitFn,
    *,
    max_repair_attempts: int = MAX_REPAIR_ATTEMPTS_DEFAULT,
) -> dict[str, Any]:
    """
    Run the orchestrator self-healing loop synchronously.

    Returns a summary dict: success, workflow, answer, attempts, healing_steps, error.
    """
    emit({"type": "status", "stage": "pipeline-start", "message": "Drafting workflow..."})

    workflow: dict | None = None
    plan: dict | None = None
    last_error = ""
    healing_steps: list[str] = []
    total_attempts = max_repair_attempts + 1
    answer_text = ""

    for attempt in range(total_attempts):
        if attempt == 0:
            emit({"type": "status", "stage": "plan", "message": "Asking Gemini..."})
            corrector_trace = None
        else:
            emit({
                "type": "status",
                "stage": "repair",
                "attempt": attempt,
                "message": f"Self-healing attempt {attempt}: {last_error[:80]}…",
            })
            corrector_trace = last_error

        prompt = _system_prompt(existing, history, message, corrector_trace)
        text = _generate(prompt)

        emit({"type": "status", "stage": "extract", "message": "Parsing response..."})
        plan = _extract_json(text)
        if not plan:
            last_error = "Gemini returned malformed JSON."
            emit({"type": "warning", "stage": "extract", "message": last_error})
            healing_steps.append("JSON parse failed")
            continue

        if plan.get("intent") == "answer_question" or not plan.get("workflow"):
            answer_text = plan.get("answer") or ""
            emit({"type": "message", "content": answer_text})
            emit({"type": "complete", "intent": "answer_question"})
            return {
                "success": True,
                "answer": answer_text,
                "workflow": None,
                "attempts": attempt + 1,
                "healing_steps": healing_steps,
            }

        workflow = plan["workflow"]

        emit({"type": "status", "stage": "validate-schema", "message": "Checking node schema..."})
        schema_err = _validate_schema(workflow)
        if schema_err:
            last_error = f"[SCHEMA VIOLATION] {schema_err}"
            emit({"type": "warning", "stage": "validate-schema", "message": last_error})
            healing_steps.append(schema_err[:100])
            continue

        emit({"type": "status", "stage": "validate-semantic", "message": "Performing dry run..."})
        sem_err = _semantic_dry_run(workflow)
        if sem_err:
            last_error = f"[SEMANTIC FAILURE] {sem_err}"
            emit({"type": "warning", "stage": "validate-semantic", "message": last_error})
            healing_steps.append(sem_err[:100])
            continue

        attempts_used = attempt + 1
        final_wf = finalize_workflow(workflow)
        answer_text = plan.get("answer") or (
            f"Built workflow '{final_wf.get('name')}' with {len(final_wf['nodes'])} nodes."
        )
        emit({"type": "status", "stage": "validated", "message": f"Validated after {attempts_used} attempt(s) ✓"})
        emit({"type": "workflow", "workflow": final_wf})
        emit({"type": "message", "content": answer_text})
        emit({"type": "complete", "attempts": attempts_used, "healingSteps": healing_steps})
        return {
            "success": True,
            "workflow": final_wf,
            "answer": answer_text,
            "attempts": attempts_used,
            "healing_steps": healing_steps,
            "validation": {"valid": True, "summary": "Validated by orchestrator pipeline"},
        }

    if workflow:
        final_wf = finalize_workflow(workflow)
        emit({"type": "warning", "stage": "exhausted", "message": last_error})
        emit({"type": "workflow", "workflow": final_wf})
        emit({"type": "complete", "attempts": total_attempts, "healingSteps": healing_steps})
        return {
            "success": False,
            "workflow": final_wf,
            "answer": f"Best-effort after {total_attempts} attempts. Last: {last_error}",
            "attempts": total_attempts,
            "healing_steps": healing_steps,
            "error": last_error,
        }

    emit({"type": "error", "stage": "exhausted", "message": last_error})
    return {
        "success": False,
        "error": last_error or "Could not produce a valid workflow",
        "attempts": total_attempts,
        "healing_steps": healing_steps,
    }
