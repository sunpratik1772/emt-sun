"""Stream workflow design and execution summaries for the Copilot UI."""
from __future__ import annotations

import json
from typing import Any, Callable, Iterator

from llm import gemini_configured, get_default_adapter

from engine.registry import NODE_SPECS

from .binding_diagnosis import diagnose_binding_issues, format_binding_diagnosis_markdown
from .run_dataset_memory import (
    dataset_memory_for_prompt,
    format_dataset_memory_markdown,
    load_run_dataset,
)
from .build_narration import (
    assumption_close_line,
    build_contextual_plan_steps,
    design_node_walkthrough_lines,
    design_summary_intro,
    pipeline_display_line,
)
from .next_action import (
    NEXT_ACTION_PROMPT,
    ensure_build_next_action_footer,
    ensure_next_action_footer,
)
from .run_verification import format_verification_markdown, run_verification

EmitChunk = Callable[[str], None]


def _compact_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for node in workflow.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        nodes.append({
            "id": node.get("id"),
            "type": node.get("type"),
            "label": node.get("label"),
            "config": node.get("config") or {},
        })
    edges = []
    for edge in workflow.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        edges.append({
            "from": edge.get("from") or edge.get("source"),
            "to": edge.get("to") or edge.get("target"),
        })
    return {
        "name": workflow.get("name"),
        "description": workflow.get("description"),
        "nodes": nodes,
        "edges": edges,
    }


def _workflow_design_system() -> str:
    return """You are Sherpa, the dbSherpa Studio workflow architect.

The user asked for a workflow. You already built a validated DAG. Explain what you
wired up the way a colleague would walk through the canvas.

Structure (markdown):
1. **{workflow name}** on its own line (bold title only).
2. Blank line, then 1–2 sentences: overall goal in plain language.
3. Blank line, then a numbered walkthrough — **one bullet per node in run order**:
   each line must say (a) the node label and friendly type (CSV Extract, Filter, Sort…),
   (b) the **exact config values** from the JSON (`source`, `expression`, `sortBy`,
   `filename`, join keys, etc.), and (c) **why** that node is there relative to the prompt.
4. Blank line, then one compact arrow summary line:
   `leads.csv` → `score ≥ 80` → `high_risk_leads_summary.csv`
5. If you assumed a vague term (e.g. high-risk → score threshold), say so in the filter line.

Rules:
- Use friendly node names (CSV Extract, Filter) — never snake_case type ids in the reply.
- Ground every value in the workflow JSON; do not invent columns or filenames.
- No "Built:", no section titled "Why these choices".
- Keep under 220 words."""
    + NEXT_ACTION_PROMPT


def _run_execution_system(*, empty_output: bool = False) -> str:
    empty_rules = (
        "5. The final output is empty — name the node that dropped rows to zero and "
        "which config value to relax (filter expression, keyword, join keys)."
        if empty_output
        else "5. Answer from dataset_memory and verification_results only — do not include SQL queries or a Suggested SQL section."
    )
    return (
        f"""You are Sherpa analyzing a completed workflow run for a surveillance analyst.

You receive the workflow definition, per-node runtime logs (row counts, samples, errors),
and a `dataset_memory` block with the full result dataset loaded in memory (row counts,
top traders, head/tail samples). Prefer `dataset_memory` for factual answers about
output content; use run_log for per-node execution status.

Write a data-focused execution summary:

Structure (markdown):
1. Title line: workflow name + "Run Summary"
2. One paragraph: overall outcome (success/partial failure) and headline metrics.
3. Numbered sections — one per executed node in order. For each:
   - **Node label (type)**: what happened, row counts, key field values from samples
   - Mention filters applied, files written, agent outputs, Teams/email stubs when present
4. Close with artifacts produced (CSV paths, response text previews).
{empty_rules}

Rules:
- Ground every claim in run_log, dataset_memory, run_facts, and verification_results JSON.
- Never output SQL blocks, ```sql fences, or a "Suggested SQL" section — verification already ran in Python.
- If verification_summary.orphan_rows is 0, do NOT suggest switching to a LEFT JOIN for coverage.
- If workflow join node already has joinType \"left\" in config, do NOT suggest changing to LEFT JOIN.
- If verification_summary.join_type_mismatch is true, mention configured vs executed join type plainly.
- Use verification_results orphan checks on alert-side columns (scenario, alert_date), never alert_id.
- If a node shows 0 rows or simulated integration, say so plainly.
- Do not invent data not in the payload.
- When the user asks for top traders or aggregates, use dataset_memory.insights.
- Keep under 400 words."""
        + NEXT_ACTION_PROMPT
    )


def _analysis_dataset_context(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        memory = load_run_dataset(workflow, run_log, run_result)
        return memory, dataset_memory_for_prompt(memory), format_dataset_memory_markdown(memory)
    except Exception:
        return {}, {}, ""


def _node_step_summary(node: dict[str, Any]) -> str:
    cfg = node.get("config") or {}
    ntype = str(node.get("type") or "")
    label = str(node.get("label") or node.get("id") or "Step")
    if ntype in ("manual_trigger", "schedule", "api_trigger", "webhook_trigger"):
        return "Start"
    if ntype in ("csv_extract", "db_query"):
        src = cfg.get("source")
        if src:
            return f"Load {src}"
        return label
    if ntype == "filter":
        expr = cfg.get("expression")
        if expr:
            return f"Filter ({expr})"
        return label
    if ntype == "sort":
        key = cfg.get("sortBy") or "column"
        order = cfg.get("order") or "asc"
        return f"Sort by {key} ({order})"
    if ntype == "join":
        lk = cfg.get("leftKey") or "key"
        return f"Join on {lk}"
    if ntype == "csv_output":
        fn = cfg.get("filename") or "CSV"
        return f"Export {fn}"
    if ntype == "excel_output":
        fn = cfg.get("filename") or "Excel"
        return f"Export {fn}"
    if ntype == "outlook":
        return "Send Outlook summary"
    return label


def _workflow_outcome_line(compact: dict[str, Any]) -> str:
    nodes = compact.get("nodes") or []
    actionable = [
        n for n in nodes
        if str(n.get("type") or "") not in (
            "manual_trigger", "schedule", "api_trigger", "webhook_trigger", "note",
        )
    ]
    node_count = len(nodes)
    edge_count = len(compact.get("edges") or [])
    chain = " → ".join(_node_step_summary(n) for n in actionable[:5])
    if chain:
        return f"{chain} · {node_count} nodes, {edge_count} edges"
    return f"{node_count} nodes, {edge_count} edges"


def _deterministic_design_summary(workflow: dict[str, Any], user_request: str) -> str:
    compact = _compact_workflow(workflow)
    name = compact.get("name") or "Workflow"
    pipeline = pipeline_display_line(compact)
    intro = design_summary_intro(user_request, compact)
    walkthrough = design_node_walkthrough_lines(user_request, compact)
    lines = [f"**{name}**", "", intro]
    if walkthrough:
        lines.extend(["", "Here's what each step does:", ""])
        lines.extend(walkthrough)
    if pipeline:
        lines.extend(["", f"At a glance: {pipeline}"])
    close = assumption_close_line(user_request, compact)
    if close and not any("high-risk" in ln.lower() or "high risk" in ln.lower() for ln in walkthrough):
        lines.extend(["", close])
    body = "\n".join(lines).strip()
    return ensure_build_next_action_footer(body, workflow=workflow, user_request=user_request)


def _deterministic_run_summary(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
    run_error: str | None = None,
) -> str:
    name = workflow.get("name") or "Workflow"
    lines = [f"**{name} — Run Summary**", ""]
    ok = [e for e in run_log if e.get("status") == "ok"]
    err = [e for e in run_log if e.get("status") == "error"]
    lines.append(
        f"Executed {len(run_log)} node(s): {len(ok)} succeeded"
        + (f", {len(err)} failed." if err else ".")
    )
    if run_error:
        lines.append(f"Run error: {run_error}")
    lines.append("")
    for idx, entry in enumerate(run_log, 1):
        label = entry.get("label") or entry.get("node_id")
        ntype = entry.get("node_type") or "node"
        dur = entry.get("duration_ms")
        dur_text = f" ({dur} ms)" if dur is not None else ""
        status = entry.get("status") or "ok"
        lines.append(f"{idx}. **{label}** (`{ntype}`){dur_text} — {status}")
        output = entry.get("output") or {}
        if isinstance(output, dict):
            if output.get("node_output"):
                snippet = json.dumps(output["node_output"], default=str)[:240]
                lines.append(f"   Output: {snippet}")
            datasets = output.get("datasets") or {}
            if isinstance(datasets, dict):
                for ds_name, ds_info in datasets.items():
                    if isinstance(ds_info, dict) and ds_info.get("rows") is not None:
                        lines.append(f"   Dataset `{ds_name}`: {ds_info['rows']} row(s)")
            if output.get("agent_response"):
                lines.append(f"   Agent: {str(output['agent_response'])[:200]}")
        if entry.get("error"):
            lines.append(f"   Error: {entry['error']}")
        lines.append("")
    binding = format_binding_diagnosis_markdown(
        diagnose_binding_issues(workflow=workflow, run_log=run_log)
    )
    if binding:
        lines.extend(["", binding])
    if run_result and run_result.get("download_url"):
        lines.append(f"Download: {run_result['download_url']}")
    _, _, memory_md = _analysis_dataset_context(workflow, run_log, run_result)
    if memory_md:
        lines.extend(["", memory_md])
    return "\n".join(lines).strip()


def _node_catalog_slice(node_types: set[str]) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for ntype in sorted(node_types):
        spec = NODE_SPECS.get(ntype)
        if not spec:
            catalog.append({"type": ntype, "status": "unknown — not in Studio palette"})
            continue
        catalog.append({
            "type": ntype,
            "description": spec.description,
            "required_params": [
                p.name for p in spec.params if p.required
            ],
            "optional_params": [
                p.name for p in spec.params if not p.required
            ][:12],
        })
    return catalog


def _failure_context_payload(
    user_request: str,
    *,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    workflow: dict[str, Any] | None = None,
    runtime_smoke_error: str | None = None,
    auto_fixes_applied: list[str] | None = None,
    attempts: int = 0,
    step_budget_hit: bool = False,
) -> dict[str, Any]:
    draft = _compact_workflow(workflow) if isinstance(workflow, dict) else None
    node_types = {
        str(n.get("type"))
        for n in (draft or {}).get("nodes") or []
        if isinstance(n, dict) and n.get("type")
    }
    return {
        "user_request": user_request.strip(),
        "attempts": attempts,
        "step_budget_hit": step_budget_hit,
        "validation_errors": errors or [],
        "validation_warnings": warnings or [],
        "runtime_smoke_error": runtime_smoke_error or "",
        "auto_fixes_applied": auto_fixes_applied or [],
        "draft_workflow": draft,
        "node_catalog": _node_catalog_slice(node_types),
    }


def _failure_diagnosis_intro(payload: dict[str, Any]) -> str:
    """One-paragraph opening that ties the failure to the user's intent."""
    request = (payload.get("user_request") or "").strip()
    errors = payload.get("validation_errors") or []
    smoke = (payload.get("runtime_smoke_error") or "").strip()
    draft = payload.get("draft_workflow") or {}
    nodes = draft.get("nodes") or []
    attempts = int(payload.get("attempts") or 0)

    intent_bits: list[str] = []
    req_lower = request.lower()
    if "comms" in req_lower or "message" in req_lower:
        intent_bits.append("monitor communications data")
    if "keyword" in req_lower or "urgent" in req_lower or "filter" in req_lower:
        intent_bits.append("apply a keyword or relevance filter")
    if "outlook" in req_lower or "email" in req_lower or "mail" in req_lower:
        intent_bits.append("notify someone via Outlook")
    intent = (
        ", then ".join(intent_bits)
        if intent_bits
        else "build the workflow you described"
    )

    blocker = ""
    if smoke:
        blocker = smoke.rstrip(".")
    elif errors:
        primary = errors[0]
        code = str(primary.get("code") or "").upper()
        node_id = primary.get("node_id")
        field = primary.get("field") or ""
        msg = str(primary.get("message") or "")
        if "outlook" in msg.lower():
            blocker = "Outlook integration is not fully configured for a live send"
        elif code == "MISSING_REQUIRED_PARAM" or "missing required" in msg.lower():
            param = field.split(".")[-1] if field else "a required field"
            node_ref = f"node `{node_id}`" if node_id else "a node"
            blocker = f"{node_ref} is missing `{param}` — the workflow cannot execute until that is set"
        elif code == "BAD_EDGE" or "sourcehandle" in msg.lower():
            blocker = "a condition branch is wired without `sourceHandle` labels (`true` / `false`)"
        elif code == "UNKNOWN_NODE" or "unknown node" in msg.lower():
            blocker = "the draft references a node type Studio does not recognize"
        elif code == "CYCLE" or "cycle" in msg.lower():
            blocker = "the graph contains a cycle, so execution order is undefined"
        else:
            blocker = msg.rstrip(".") or "validation rejected the draft before it could run"
    elif payload.get("step_budget_hit"):
        blocker = "the builder exhausted its step budget before reaching a valid DAG"
    else:
        blocker = "the draft did not pass validation"

    draft_note = ""
    if nodes:
        draft_note = (
            f" Sherpa did assemble a partial design ({len(nodes)} node"
            f"{'s' if len(nodes) != 1 else ''}), but it is not safe to load on the canvas yet."
        )
    elif attempts > 1:
        draft_note = f" After {attempts} repair passes, no runnable graph was produced."

    return (
        f"I understood your goal: **{intent}**. "
        f"The blocker is that **{blocker}**.{draft_note}"
    )


def _humanize_validation_error(err: dict[str, Any], draft: dict[str, Any] | None) -> str:
    """Translate a validation record into analyst-facing language."""
    code = str(err.get("code") or "ERROR")
    node_id = err.get("node_id")
    field = str(err.get("field") or "")
    msg = str(err.get("message") or "")

    node_label = node_id
    node_type = ""
    if draft and node_id:
        for n in draft.get("nodes") or []:
            if isinstance(n, dict) and n.get("id") == node_id:
                node_label = n.get("label") or node_id
                node_type = str(n.get("type") or "")
                break

    node_ref = f"**{node_label}**"
    if node_type:
        node_ref += f" (`{node_type}`)"

    param = field.split(".")[-1] if field else ""
    if code == "MISSING_REQUIRED_PARAM" or "missing required" in msg.lower():
        if param:
            return f"{node_ref} cannot run without `{param}` configured."
        return f"{node_ref} is missing required configuration."
    if "sourcehandle" in msg.lower() or code == "BAD_EDGE":
        return (
            f"{node_ref} has a branch edge that must declare "
            f"`sourceHandle: \"true\"` or `\"false\"` so the runner knows which path to take."
        )
    if "outlook" in msg.lower() or node_type == "outlook":
        return f"{node_ref} — {msg.rstrip('.')}. Outlook also needs Graph credentials in the backend environment."
    if node_id:
        return f"{node_ref} — {msg.rstrip('.')}."
    return msg.rstrip(".") + "." if msg else f"`{code}` validation failure."


def _failure_recovery_steps(payload: dict[str, Any]) -> list[str]:
    """Context-aware recovery actions ordered by likely impact."""
    request = (payload.get("user_request") or "").lower()
    errors = payload.get("validation_errors") or []
    smoke = (payload.get("runtime_smoke_error") or "").lower()
    catalog = {e["type"]: e for e in (payload.get("node_catalog") or []) if e.get("type")}
    steps: list[str] = []

    err_text = " ".join(
        str(e.get("message") or "") + " " + str(e.get("code") or "") for e in errors
    ).lower()
    needs_outlook = (
        "outlook" in request
        or "email" in request
        or "outlook" in err_text
        or "outlook" in smoke
        or "outlook" in catalog
    )
    needs_condition_fix = "sourcehandle" in err_text or "bad_edge" in err_text
    needs_comms = "comms" in request or "comms_messages" in err_text

    if needs_outlook and ("credential" in smoke or "tenant" in smoke or "outlook" in smoke):
        steps.append(
            "Configure Outlook in the backend `.env` (`OUTLOOK_TENANT_ID`, client id/secret, or the "
            "tenant override on the Outlook node), then retry — without credentials the send step cannot pass smoke test."
        )
    if needs_comms:
        steps.append(
            "Confirm `comms_messages` is available as a data source and name the filter column explicitly "
            "(e.g. `keyword = 'urgent'`) so the read → filter → notify chain is unambiguous."
        )
    for err in errors:
        field = str(err.get("field") or "")
        param = field.split(".")[-1]
        node_id = err.get("node_id")
        if param and node_id:
            steps.append(
                f"Set `{param}` on node `{node_id}` — for email alerts that is typically the recipient, "
                f"subject line, and a body template referencing message fields."
            )
            break
    if needs_condition_fix:
        steps.append(
            "Re-wire condition outputs so the **Yes** path uses `sourceHandle: \"true\"` and the **No** path "
            "uses `\"false\"` — Run validation requires this even when the canvas looks connected."
        )
    if (payload.get("draft_workflow") or {}).get("nodes"):
        steps.append(
            "Paste a follow-up like: *\"Fix the draft using the validation errors above — keep comms_messages "
            "as the source and send Outlook to analyst@example.com with message details.\"*"
        )
    else:
        steps.append(
            "Retry with a tighter prompt: source table, filter expression, recipient, and subject line in one sentence."
        )
    if not steps:
        steps.append(
            "Review the validation errors above, adjust node config or env vars, and ask Sherpa to repair the draft."
        )
    seen: set[str] = set()
    unique: list[str] = []
    for s in steps:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:5]


def _generation_failure_system() -> str:
    return """You are Sherpa, a senior workflow architect at dbSherpa Studio.

The user asked for a workflow; generation failed before a runnable DAG could be loaded on the canvas.
Write a post-mortem that sounds like you personally traced the failure — confident, specific, actionable.

Voice:
- Lead with insight, not headers. Sound like a colleague who already debugged this.
- Tie every error to what the user was trying to accomplish (monitor data → filter → act).
- Prefer "the Outlook step cannot send because credentials are missing" over repeating error codes.
- When quoting errors, translate jargon into plain analyst language immediately after.

Structure (markdown):
1. **Diagnosis** — 2–3 sentences: restate the user's intent, name the primary blocker, note whether a partial draft exists.
2. **What went wrong** — 3–5 bullets; each names the node (label + type), the violated constraint, and why it breaks this pipeline.
3. **Draft walkthrough** — if nodes exist, describe them in execution order and flag missing config or wiring gaps.
4. **Integration & node requirements** — only for involved types: required params, env vars, data source columns.
5. **Recovery path** — numbered fixes ordered fastest-first; end with a copy-paste follow-up prompt for Sherpa.

Rules:
- Ground every claim in the supplied JSON only — do not invent nodes or errors.
- If the request mentions comms_messages, keyword filters, or Outlook, reason about that pipeline explicitly.
- Never mention harness, validators, orchestrator, or internal tooling unless step_budget_hit is true.
- Do not apologize excessively; be direct and helpful.
- Under 450 words."""
    + NEXT_ACTION_PROMPT


def _deterministic_failure_summary(payload: dict[str, Any]) -> str:
    draft = payload.get("draft_workflow")
    errors = payload.get("validation_errors") or []
    smoke = (payload.get("runtime_smoke_error") or "").strip()
    fixes = payload.get("auto_fixes_applied") or []
    catalog = payload.get("node_catalog") or []

    lines = [
        _failure_diagnosis_intro(payload),
        "",
    ]

    if errors or smoke:
        lines.append("**What went wrong**")
        for err in errors[:8]:
            lines.append(f"- {_humanize_validation_error(err, draft)}")
        if smoke and not any(smoke.lower() in str(e.get("message", "")).lower() for e in errors):
            lines.append(f"- **Runtime check:** {smoke.rstrip('.')}.")
        lines.append("")

    if fixes:
        lines.append(f"**Repair attempts:** Sherpa already tried {len(fixes)} automatic fix"
                      f"{'es' if len(fixes) != 1 else ''} ({'; '.join(fixes[:4])}).")
        lines.append("")

    if draft and draft.get("nodes"):
        lines.append("**Draft walkthrough**")
        for idx, node in enumerate(draft["nodes"], 1):
            cfg = node.get("config") or {}
            cfg_bits = [f"{k}={v!r}" for k, v in list(cfg.items())[:4]]
            cfg_text = f" — config: {', '.join(cfg_bits)}" if cfg_bits else " — config incomplete"
            lines.append(
                f"{idx}. **{node.get('label') or node.get('id')}** (`{node.get('type')}`){cfg_text}"
            )
        edge_count = len(draft.get("edges") or [])
        if edge_count:
            lines.append(f"   ({edge_count} edge{'s' if edge_count != 1 else ''} between nodes)")
        lines.append("")

    if catalog:
        lines.append("**Node & integration context**")
        for entry in catalog[:8]:
            if entry.get("status"):
                lines.append(f"- `{entry['type']}` — {entry['status']}.")
            else:
                req = ", ".join(f"`{p}`" for p in (entry.get("required_params") or [])) or "none"
                desc = (entry.get("description") or "").strip()
                lines.append(f"- `{entry['type']}` — {desc} Required: {req}.")
        lines.append("")

    recovery = _failure_recovery_steps(payload)
    lines.append("**Recovery path**")
    for idx, step in enumerate(recovery, 1):
        lines.append(f"{idx}. {step}")

    from .next_action import ensure_failure_next_action_footer

    body = "\n".join(lines)
    return ensure_failure_next_action_footer(
        body,
        user_request=str(payload.get("user_request") or ""),
        payload=payload,
    )


def stream_generation_failure_summary(
    user_request: str,
    *,
    errors: list[dict[str, Any]] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    workflow: dict[str, Any] | None = None,
    runtime_smoke_error: str | None = None,
    auto_fixes_applied: list[str] | None = None,
    attempts: int = 0,
    step_budget_hit: bool = False,
    planning_monologue: str | None = None,
) -> Iterator[str]:
    """Stream a failure post-mortem with validation context and fix suggestions."""
    payload = _failure_context_payload(
        user_request,
        errors=errors,
        warnings=warnings,
        workflow=workflow,
        runtime_smoke_error=runtime_smoke_error,
        auto_fixes_applied=auto_fixes_applied,
        attempts=attempts,
        step_budget_hit=step_budget_hit,
    )
    if not gemini_configured():
        yield _deterministic_failure_summary(payload)
        return

    adapter = get_default_adapter()
    plan_block = ""
    if (planning_monologue or "").strip():
        plan_block = (
            "Sherpa planning (binding — the recovery summary must follow this):\n"
            f"{planning_monologue.strip()}\n\n"
        )
    prompt = (
        f"{plan_block}"
        "Generation failure context (JSON):\n"
        f"{json.dumps(payload, indent=2, default=str)[:14000]}"
    )
    fallback = _deterministic_failure_summary(payload)
    emitted = False
    try:
        for chunk in adapter.chat_turn_stream(
            system_prompt=_generation_failure_system(),
            history=[],
            user_turn=prompt,
            temperature=0.2,
            json_mode=False,
        ):
            if chunk:
                emitted = True
                yield chunk
    except Exception:
        if not emitted:
            yield fallback
        return
    if not emitted:
        yield fallback


def stream_workflow_design_summary(
    workflow: dict[str, Any],
    user_request: str,
) -> Iterator[str]:
    """Emit the design summary (deterministic, question-aware rationale)."""
    text = _deterministic_design_summary(workflow, user_request)
    chunk_size = 56
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def _compact_run_log_for_prompt(run_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shrink run_log for LLM prompts — drop full row payloads, keep counts."""
    compact: list[dict[str, Any]] = []
    for entry in run_log[:30]:
        if not isinstance(entry, dict):
            continue
        slim: dict[str, Any] = {
            k: entry.get(k)
            for k in (
                "node_id", "node_type", "label", "status", "duration_ms", "error", "index", "total",
            )
            if entry.get(k) is not None
        }
        output = entry.get("output")
        if isinstance(output, dict):
            node_output = output.get("node_output")
            if isinstance(node_output, dict):
                rows = node_output.get("rows")
                slim_output: dict[str, Any] = {}
                if isinstance(rows, list):
                    slim_output["row_count"] = len(rows)
                    slim_output["sample_rows"] = rows[:2]
                elif node_output.get("rowCount") is not None:
                    slim_output["row_count"] = node_output.get("rowCount")
                for key in ("joinType", "leftKey", "rightKey"):
                    if node_output.get(key) is not None:
                        slim_output[key] = node_output.get(key)
                slim["output"] = {"node_output": slim_output}
        compact.append(slim)
    return compact


def _run_analysis_prompt(
    payload: dict[str, Any],
    *,
    user_message: str | None = None,
    suggested_sql: str | None = None,
    planning_monologue: str | None = None,
) -> str:
    body = json.dumps(payload, indent=2, default=str)[:14000]
    question = (user_message or "").strip()
    parts: list[str] = []
    if (planning_monologue or "").strip():
        parts.append(
            "Sherpa planning (binding — the run summary must follow this):\n"
            f"{planning_monologue.strip()}"
        )
    if question:
        parts.append(f"User question:\n{question}")
    verification = payload.get("verification_results")
    if verification:
        parts.append(
            "Deterministic verification already executed — use these results; "
            "do not contradict them:\n"
            f"{json.dumps(verification, indent=2, default=str)[:4000]}"
        )
    diagnosis = payload.get("empty_output_diagnosis")
    if diagnosis:
        parts.append(
            "Empty output diagnosis (binding — focus next-step advice here):\n"
            f"{json.dumps(diagnosis, indent=2)}"
        )
    if (payload.get("output_row_count") or 0) == 0 or (payload.get("verification_summary") or {}).get(
        "total_rows"
    ) == 0:
        parts.append(
            "Final run_output has zero rows — explain which node zeroed the pipeline and what to relax."
        )
    if parts:
        return "\n\n".join(parts) + f"\n\nAnalyze this completed run:\n{body}"
    return f"Analyze this completed run:\n{body}"


def _empty_run_review_message(
    workflow: dict[str, Any],
    route_metadata: dict[str, Any] | None = None,
) -> str:
    meta = route_metadata or {}
    wf_name = str(workflow.get("name") or meta.get("workflow_name") or "this workflow").strip()
    return (
        f'No run history found for **{wf_name}**.\n\n'
        "Sherpa needs at least one completed run with per-node logs before it can review reliability "
        "or suggest a concrete fix. Use **Run** in the top bar (or ask Sherpa to run a sample), "
        "then ask again."
    )


def stream_run_execution_summary(
    workflow: dict[str, Any],
    run_log: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
    emit_chunk: EmitChunk,
    *,
    run_error: str | None = None,
    user_message: str | None = None,
    suggested_sql: str | None = None,
    route_metadata: dict[str, Any] | None = None,
    planning_monologue: str | None = None,
) -> str:
    """Stream (or emit once) a post-run analysis. Returns full text."""
    if not run_log:
        text = _empty_run_review_message(workflow, route_metadata)
        text = ensure_next_action_footer(
            text,
            workflow=workflow,
            verification={"output_row_count": 0, "verification_summary": {"total_rows": 0}},
            user_message=user_message or "",
        )
        emit_chunk(text)
        return text

    _, dataset_blob, memory_md = _analysis_dataset_context(workflow, run_log, run_result)
    verification = run_verification(
        workflow,
        run_log,
        run_result,
        user_message=user_message,
        route_metadata=route_metadata,
    )
    verification_md = format_verification_markdown(verification)
    empty_output = (verification.get("output_row_count") or 0) == 0

    if not gemini_configured():
        text = _deterministic_run_summary(workflow, run_log, run_result, run_error=run_error)
        if (user_message or "").strip() and memory_md:
            text = f"**Your question:** {(user_message or '').strip()}\n\n{text}\n\n{memory_md}"
        if verification_md:
            text = f"{text}\n\n{verification_md}"
        text = ensure_next_action_footer(
            text, workflow=workflow, verification=verification, user_message=user_message or "",
        )
        emit_chunk(text)
        return text

    # Sparse logs without loaded data → deterministic only.
    has_dataset = bool(dataset_blob.get("row_count"))
    if run_error or (len(run_log) <= 1 and not has_dataset):
        text = _deterministic_run_summary(workflow, run_log, run_result, run_error=run_error)
        if verification_md:
            text = f"{text}\n\n{verification_md}"
        text = ensure_next_action_footer(
            text, workflow=workflow, verification=verification, user_message=user_message or "",
        )
        emit_chunk(text)
        return text

    adapter = get_default_adapter()
    payload = {
        "workflow": _compact_workflow(workflow),
        "run_log": _compact_run_log_for_prompt(run_log),
        "run_result": run_result or {},
        "run_error": run_error or "",
        "dataset_memory": dataset_blob,
        "run_facts": verification.get("run_facts") or {},
        "verification_summary": verification.get("verification_summary") or {},
        "verification_results": verification.get("verification_results") or [],
        "output_row_count": verification.get("output_row_count"),
        "empty_output_diagnosis": verification.get("empty_output_diagnosis"),
    }
    prompt = _run_analysis_prompt(
        payload,
        user_message=user_message,
        suggested_sql=suggested_sql,
        planning_monologue=planning_monologue,
    )

    try:
        reply = adapter.chat_turn(
            system_prompt=_run_execution_system(empty_output=empty_output),
            history=[],
            user_turn=prompt,
            temperature=0.2,
            json_mode=False,
        )
        text = reply or _deterministic_run_summary(workflow, run_log, run_result, run_error=run_error)
        from copilot.next_action import strip_suggested_sql_sections

        text = strip_suggested_sql_sections(text)
        text = ensure_next_action_footer(
            text, workflow=workflow, verification=verification, user_message=user_message or "",
        )
        emit_chunk(text)
        return text
    except Exception:
        text = _deterministic_run_summary(workflow, run_log, run_result, run_error=run_error)
        text = ensure_next_action_footer(
            text, workflow=workflow, verification=verification, user_message=user_message or "",
        )
        emit_chunk(text)
        return text
