"""Next-step closers for Sherpa replies + follow-up resolution for 'do it'."""
from __future__ import annotations

import re
from typing import Any

NEXT_ACTION_PROMPT = """
End EVERY reply with a **Next step:** section (required — two lines):
1. One sentence: the single most likely action Sherpa should take next (imperative, specific).
2. One short question the user can answer with "do it", "yes", or "go ahead".

Example:
**Next step:** Update the join node so it executes as a left join, matching the workflow config.
Want me to apply that fix on the canvas?

Rules:
- The question must refer to the action on line 1 — never a generic "anything else?".
- If you suggested a workflow change, the next step MUST be applying that change on the canvas.
- If the run looks healthy and no fix is needed, offer the most useful follow-up (re-run, export tweak, etc.).
"""

_NEXT_STEP_RE = re.compile(
    r"(?:\*\*)?Next step:(?:\*\*)?\s*(.+?)(?:\n\n|\n)(.+?)(?:\n\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_SAMPLE_RUN_QUESTION_RE = re.compile(
    r"want me to (?:start a )?sample run|run (?:it|the workflow).{0,40}sample data",
    re.IGNORECASE,
)


def format_next_action_block(action: str, question: str) -> str:
    action = (action or "").strip().rstrip(".")
    question = (question or "").strip()
    if not question.endswith("?"):
        question = question.rstrip(".") + "?"
    return f"**Next step:** {action}.\n\n{question}"


def parse_next_action_from_text(text: str) -> tuple[str | None, str | None]:
    """Extract (action, question) from the last Next step block in assistant text."""
    raw = (text or "").strip()
    if not raw:
        return None, None
    matches = list(_NEXT_STEP_RE.finditer(raw))
    if matches:
        m = matches[-1]
        action = m.group(1).strip().strip(".")
        question = m.group(2).strip().splitlines()[0].strip()
        return action or None, question or None
    return _infer_next_step_from_tail(raw)


def _infer_next_step_from_tail(text: str) -> tuple[str | None, str | None]:
    """Recover sample-run offers when the Next step header was truncated from thread context."""
    tail = text[-700:] if len(text) > 700 else text
    if not _SAMPLE_RUN_QUESTION_RE.search(tail):
        return None, None
    lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
    question = next(
        (ln for ln in reversed(lines) if "?" in ln and _SAMPLE_RUN_QUESTION_RE.search(ln)),
        None,
    )
    if not question:
        question = next((ln for ln in reversed(lines) if "?" in ln), None)
    action = None
    for ln in reversed(lines):
        lower = ln.lower()
        if ln == question:
            continue
        if lower.startswith("next step:"):
            action = re.sub(r"^(?:\*\*)?Next step:(?:\*\*)?\s*", "", ln, flags=re.IGNORECASE).strip().strip(".")
            break
        if "sample data" in lower and ("run " in lower or lower.startswith("run ")):
            action = ln.strip("*").strip()
            break
    if not action:
        action = "Run the workflow on canvas with sample data"
    return action, question


def last_assistant_turn(thread_context: str) -> str:
    """Return the most recent Sherpa message body from formatted thread context."""
    text = (thread_context or "").strip()
    if not text:
        return ""
    chunks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("Sherpa:"):
            if current:
                chunks.append("\n".join(current))
            current = [line.removeprefix("Sherpa:").strip()]
        elif line.startswith("User:"):
            if current:
                chunks.append("\n".join(current))
                current = []
        elif current:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks[-1] if chunks else text


def pending_action_from_thread(thread_context: str) -> str | None:
    """Concrete build instruction from the last **Next step:** offer."""
    assistant = last_assistant_turn(thread_context)
    action, question = parse_next_action_from_text(assistant)
    if not action:
        return None
    if question:
        return f"{action}. {question.rstrip('?')}."
    return action


_CREATE_ON_CANVAS_RE = re.compile(
    r"want me to create|should I create|create .{0,80} on the canvas",
    re.IGNORECASE,
)


def is_create_workflow_next_step(action: str | None, question: str | None) -> bool:
    """True when Sherpa offered to create a new workflow on the canvas after a plan."""
    blob = f"{action or ''} {question or ''}"
    return bool(_CREATE_ON_CANVAS_RE.search(blob))


def is_canvas_edit_next_step(action: str | None, question: str | None) -> bool:
    """True when Sherpa offered a canvas edit, not executing a sample run."""
    q = (question or "").lower()
    a = (action or "").lower()
    if any(
        phrase in q
        for phrase in (
            "apply that change",
            "apply that fix",
            "make that change",
            "adjust a step",
            "on the canvas",
        )
    ):
        return True
    if any(phrase in a for phrase in ("loosen", "adjust **", "review the join", "fix node")):
        return True
    return False


def is_sample_run_next_step(action: str | None, question: str | None) -> bool:
    """True when the offered next step is executing the workflow, not editing it."""
    if is_canvas_edit_next_step(action, question):
        return False
    q = (question or "").lower()
    a = (action or "").lower()
    if "sample run" in q or "start a sample run" in q:
        return True
    if a.startswith("run ") and "sample data" in a and "adjust" not in q:
        return True
    if "re-run" in a and "sample data" in a and "adjust" not in q:
        return True
    return False


def last_next_step_from_thread(thread_context: str) -> tuple[str | None, str | None]:
    """(action, question) from the last Sherpa **Next step:** block."""
    return parse_next_action_from_text(last_assistant_turn(thread_context))


def _empty_run_verification(verification: dict[str, Any] | None) -> bool:
    summary = (verification or {}).get("verification_summary") or {}
    output_rows = summary.get("total_rows")
    if output_rows is None:
        output_rows = (verification or {}).get("output_row_count")
    diagnosis = (verification or {}).get("empty_output_diagnosis")
    return output_rows == 0 or bool(diagnosis)


def strip_next_action_block(text: str) -> str:
    """Remove the last **Next step:** block so it can be replaced."""
    raw = (text or "").strip()
    if not raw:
        return raw
    matches = list(_NEXT_STEP_RE.finditer(raw))
    if not matches:
        return raw
    return raw[: matches[-1].start()].rstrip()


_SUGGESTED_SQL_SECTION_RE = re.compile(
    r"(?:\n|^)\s*\*{0,2}Suggested SQL[\s\S]*?```[\s\S]*?```",
    re.IGNORECASE,
)


def strip_suggested_sql_sections(text: str) -> str:
    """Drop Suggested SQL blocks from run summaries."""
    body = (text or "").strip()
    if not body:
        return body
    cleaned = _SUGGESTED_SQL_SECTION_RE.sub("", body)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def infer_run_review_next_action(
    workflow: dict[str, Any],
    verification: dict[str, Any] | None,
    *,
    user_message: str = "",
) -> str | None:
    """Deterministic next-step when LLM path is unavailable."""
    summary = (verification or {}).get("verification_summary") or {}
    wf_name = str(workflow.get("name") or "the workflow").strip()
    lower = (user_message or "").lower()

    if summary.get("join_type_mismatch"):
        join_label = "the join node"
        for node in workflow.get("nodes") or []:
            if isinstance(node, dict) and node.get("type") == "join":
                join_label = str(node.get("label") or join_label)
                break
        return format_next_action_block(
            f"Update **{join_label}** in **{wf_name}** so `joinType` left is executed as a left join",
            "Want me to apply that fix on the canvas",
        )

    if any(k in lower for k in ("suggest", "improve", "reliability", "fix", "change")):
        return format_next_action_block(
            f"Apply the top reliability improvement for **{wf_name}** on the canvas",
            "Want me to make that change now",
        )

    output_rows = summary.get("total_rows")
    if output_rows is None:
        output_rows = (verification or {}).get("output_row_count")
    diagnosis = (verification or {}).get("empty_output_diagnosis")
    if output_rows == 0 or diagnosis:
        label = str((diagnosis or {}).get("label") or "the step that produced zero rows")
        ntype = str((diagnosis or {}).get("node_type") or "")
        expr = (diagnosis or {}).get("expression")
        if ntype == "filter" and expr:
            action = (
                f"Loosen the filter on **{label}** in **{wf_name}** "
                f"(current expression may be too strict: `{expr[:120]}`)"
            )
        elif ntype == "join":
            action = (
                f"Review the join on **{label}** in **{wf_name}** — "
                f"keys or join type may be dropping all rows"
            )
        else:
            action = (
                f"Adjust **{label}** in **{wf_name}** so rows reach the export "
                f"(run output is empty)"
            )
        return format_next_action_block(
            action,
            "Want me to apply that change on the canvas",
        )

    return format_next_action_block(
        f"Re-run **{wf_name}** with sample data to confirm the output",
        "Want me to start a sample run now",
    )


def ensure_next_action_footer(
    text: str,
    *,
    workflow: dict[str, Any],
    verification: dict[str, Any] | None = None,
    user_message: str = "",
) -> str:
    """Append or correct the **Next step:** block after a run review."""
    body = (text or "").strip()
    if not body:
        return body

    empty_run = _empty_run_verification(verification)
    if empty_run:
        body = strip_suggested_sql_sections(body)

    action, question = parse_next_action_from_text(body)
    if empty_run:
        # Model often offers re-run + fake SQL when output is empty — replace with adjust-step.
        body = strip_next_action_block(body)
        action, question = None, None
    elif action:
        return body

    block = infer_run_review_next_action(workflow, verification, user_message=user_message)
    if block:
        return f"{body}\n\n{block}"
    return body


def infer_build_next_action(
    workflow: dict[str, Any],
    *,
    user_request: str = "",
) -> str:
    """Next step after a successful workflow build."""
    name = str(workflow.get("name") or "the workflow").strip()
    lower = (user_request or "").lower()
    if any(k in lower for k in ("export", "excel", "csv", "report", "summary")):
        return format_next_action_block(
            f"Run **{name}** with sample data to preview the export",
            "Want me to start a sample run now",
        )
    if any(k in lower for k in ("filter", "join", "sort", "aggregate", "score")):
        return format_next_action_block(
            f"Run **{name}** with sample data to verify the pipeline output",
            "Want me to start a sample run now",
        )
    return format_next_action_block(
        f"Run **{name}** on the canvas with sample data",
        "Want me to start a sample run now",
    )


def ensure_build_next_action_footer(
    text: str,
    *,
    workflow: dict[str, Any],
    user_request: str = "",
) -> str:
    """Append a Next step block to build replies if the model omitted it."""
    body = (text or "").strip()
    if not body:
        return body
    if parse_next_action_from_text(body)[0]:
        return body
    block = infer_build_next_action(workflow, user_request=user_request)
    return f"{body}\n\n{block}"


def infer_ask_next_action(
    user_message: str = "",
    *,
    workflow: dict[str, Any] | None = None,
) -> str:
    """Next step after an Ask-mode reply."""
    lower = (user_message or "").lower()
    wf_name = str((workflow or {}).get("name") or "the workflow").strip()
    if any(k in lower for k in ("build", "create", "make", "pipeline", "workflow")):
        return format_next_action_block(
            "Describe the pipeline you want and I'll draft it on the canvas",
            "Want me to build that workflow now",
        )
    if any(k in lower for k in ("fix", "error", "fail", "broken", "repair")):
        return format_next_action_block(
            f"Apply the top fix to **{wf_name}** on the canvas",
            "Want me to make that change now",
        )
    if workflow and wf_name not in ("the workflow", ""):
        return format_next_action_block(
            f"Run **{wf_name}** with sample data to verify the output",
            "Want me to start a sample run now",
        )
    return format_next_action_block(
        "Describe the workflow change or run you want next",
        "Want me to build or fix that on the canvas",
    )


def infer_load_next_action(
    *,
    query: str = "",
    loaded_name: str | None = None,
    found: bool = True,
) -> str:
    """Next step after a load / disambiguation reply."""
    if found and loaded_name:
        return format_next_action_block(
            f"Review **{loaded_name}** on the canvas and run a sample execution",
            "Want me to start a sample run now",
        )
    if not found:
        return format_next_action_block(
            f"Build a new pipeline matching **{query or 'your request'}** on the canvas",
            "Want me to draft that workflow now",
        )
    return format_next_action_block(
        "Reply with the workflow name or number to load it onto the canvas",
        "Want me to build a new pipeline instead",
    )


def infer_automate_next_action(
    automation_name: str,
    *,
    schedule_summary: str = "",
) -> str:
    """Next step after automation creation."""
    sched = f" ({schedule_summary})" if schedule_summary else ""
    return format_next_action_block(
        f"Open **Automations** to review **{automation_name}**{sched}",
        "Want me to adjust the schedule or workflow steps",
    )


def infer_failure_next_action(
    user_request: str = "",
    *,
    payload: dict[str, Any] | None = None,
) -> str:
    """Next step after a failed workflow build."""
    draft = (payload or {}).get("draft_workflow") if isinstance(payload, dict) else None
    name = str((draft or {}).get("name") or "the workflow").strip()
    lower = (user_request or "").lower()
    if any(k in lower for k in ("join", "filter", "outlook", "export", "csv")):
        return format_next_action_block(
            f"Retry **{name}** with the top recovery fix applied on the canvas",
            "Want me to apply that fix and regenerate",
        )
    return format_next_action_block(
        f"Retry the build for **{name}** with the recovery fixes applied",
        "Want me to apply the top fix and regenerate",
    )


def _append_footer_if_missing(text: str, block: str) -> str:
    body = (text or "").strip()
    if not body:
        return body
    if parse_next_action_from_text(body)[0]:
        return body
    return f"{body}\n\n{block}"


def ensure_ask_next_action_footer(
    text: str,
    *,
    user_message: str = "",
    workflow: dict[str, Any] | None = None,
) -> str:
    return _append_footer_if_missing(
        text,
        infer_ask_next_action(user_message, workflow=workflow),
    )


def ensure_load_next_action_footer(
    text: str,
    *,
    query: str = "",
    loaded_name: str | None = None,
    found: bool = True,
) -> str:
    return _append_footer_if_missing(
        text,
        infer_load_next_action(query=query, loaded_name=loaded_name, found=found),
    )


def ensure_automate_next_action_footer(
    text: str,
    *,
    automation_name: str,
    schedule_summary: str = "",
) -> str:
    return _append_footer_if_missing(
        text,
        infer_automate_next_action(automation_name, schedule_summary=schedule_summary),
    )


def ensure_failure_next_action_footer(
    text: str,
    *,
    user_request: str = "",
    payload: dict[str, Any] | None = None,
) -> str:
    return _append_footer_if_missing(
        text,
        infer_failure_next_action(user_request, payload=payload),
    )
