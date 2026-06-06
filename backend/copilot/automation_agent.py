"""Copilot automation orchestration — save workflow, create schedule, optional test run."""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, Iterator

from generation.harness.intent import _BUILD_COMMAND
from app.database import save_automation, save_workflow_db, get_workflow_db
from app.scheduler import execute_automation_workflow
from copilot.schedule_parser import parse_schedule_from_text, wants_test_run
from copilot.thread_context import thread_references_recent_workflow

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", (name or "workflow").lower()).strip("-")
    return slug or "workflow"


def should_build_workflow_first(
    message: str,
    current_workflow: dict | None,
    *,
    thread_context: str | None = None,
) -> bool:
    lower = (message or "").lower()
    if re.search(
        r"\b(this|current|just created|you just created|on the canvas|loaded)\b.{0,40}\b(workflow|pipeline|automation)\b",
        lower,
    ):
        return False
    if re.search(r"\b(automation of the workflow that you just created)\b", lower):
        return False
    if re.search(r"\b(what you just built|pipeline you just|workflow you just)\b", lower):
        return False
    if thread_references_recent_workflow(thread_context or "") and not current_workflow:
        return False
    if not current_workflow:
        return bool(_BUILD_COMMAND.search(message or "")) or bool(
            re.search(r"\b(take .+ from .+|workflow which will|pipeline that)\b", lower)
        )
    if re.search(r"\b(take .+ from .+ and .+|workflow which will|pipeline that)\b", lower):
        return True
    return False


def derive_automation_name(message: str, workflow: dict | None) -> str:
    if workflow and workflow.get("name"):
        return f"{workflow['name']} Automation"
    snippet = re.sub(r"\s+", " ", (message or "").strip())[:72]
    return snippet or "Scheduled Automation"


def save_workflow_for_automation(dag: dict[str, Any]) -> str:
    """Persist workflow for automation scheduling — database only."""
    from app.request_context import get_current_user_id

    user_id = get_current_user_id()
    slug = _slugify(str(dag.get("name") or dag.get("workflow_id") or "workflow"))
    filename = f"{slug}.json"
    counter = 1
    while get_workflow_db(filename, user_id):
        filename = f"{slug}-{counter}.json"
        counter += 1
    save_workflow_db(
        filename=filename,
        workflow_id=dag.get("workflow_id"),
        name=dag.get("name"),
        description=dag.get("description"),
        workflow_data=json.dumps(dag),
        user_id=user_id,
    )
    return filename


def _trigger_test_run(auto_row: dict[str, Any]) -> None:
    """Run automation once — works from sync generator context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(execute_automation_workflow(auto_row))
        return
    loop.create_task(execute_automation_workflow(auto_row))


def run_automation_flow_stream(
    *,
    message: str,
    current_workflow: dict | None,
    generate_workflow: Any,
    generate_workflow_stream: Any | None = None,
    thread_context: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield SSE-style events for automation creation (+ optional workflow build)."""
    from copilot.thinking_monologue import ThinkingMonologueContext
    from copilot.next_action import ensure_automate_next_action_footer
    from copilot.thinking_sse import yield_llm_thinking_monologue

    workflow = current_workflow
    build_first = should_build_workflow_first(
        message,
        current_workflow,
        thread_context=thread_context,
    )
    ctx = ThinkingMonologueContext.for_automate(
        message,
        workflow=workflow,
        build_first=build_first,
    )
    yield from yield_llm_thinking_monologue(ctx)

    if build_first:
        if generate_workflow_stream is not None:
            built: dict | None = None
            for event in generate_workflow_stream(message, current_workflow=current_workflow):
                if isinstance(event, dict):
                    yield event
                    if event.get("type") == "workflow_created" and isinstance(event.get("workflow"), dict):
                        built = event["workflow"]
            if not built:
                return
            workflow = built
        else:
            result = generate_workflow(message, current_workflow=current_workflow)
            if not result.get("success") or not result.get("workflow"):
                yield {
                    "type": "error",
                    "message": result.get("error") or "Could not build a workflow for this automation.",
                }
                return
            workflow = result["workflow"]
            yield {
                "type": "workflow_created",
                "name": workflow.get("name") or "Workflow",
                "nodeCount": len(workflow.get("nodes") or []),
                "workflow": workflow,
            }

    if not workflow or not workflow.get("nodes"):
        yield {
            "type": "error",
            "message": "No workflow is loaded. Build or load a workflow first, then ask me to automate it.",
        }
        return

    filename = save_workflow_for_automation(workflow)

    schedule = parse_schedule_from_text(message)

    auto_name = derive_automation_name(message, workflow)
    automation_id = f"auto_{uuid.uuid4().hex[:12]}"

    save_automation(
        automation_id=automation_id,
        name=auto_name,
        workflow_filename=filename,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_mins=schedule.interval_mins,
        duration_mins=schedule.duration_mins,
        active=True,
        author="Copilot",
        output_filename_pattern=None,
    )

    yield {
        "type": "automation_created",
        "automation_id": automation_id,
        "name": auto_name,
        "workflow_filename": filename,
        "schedule_type": schedule.schedule_type,
        "cron_expression": schedule.cron_expression,
        "interval_mins": schedule.interval_mins,
        "duration_mins": schedule.duration_mins,
        "schedule_summary": schedule.summary,
        "timezone_note": schedule.timezone_note,
    }

    test = wants_test_run(message)
    if test:
        auto_row = {
            "id": automation_id,
            "name": auto_name,
            "workflow_filename": filename,
            "schedule_type": schedule.schedule_type,
            "cron_expression": schedule.cron_expression,
            "interval_mins": schedule.interval_mins,
            "duration_mins": schedule.duration_mins,
            "active": True,
        }
        _trigger_test_run(auto_row)
        yield {"type": "test_run_started", "automation_id": automation_id}

    bullets = [
        f"Saved workflow as `{filename}`",
        f"Created automation **{auto_name}**",
        f"Schedule: {schedule.summary} ({schedule.timezone_note})",
    ]
    if test:
        bullets.append("Started a test run — check Automations for live status.")

    reply = ensure_automate_next_action_footer(
        (
            f"Done — **{auto_name}** is scheduled: {schedule.summary}.\n\n"
            + "\n".join(f"- {b}" for b in bullets if not b.startswith("Open"))
        ),
        automation_name=auto_name,
        schedule_summary=schedule.summary,
    )
    yield {"type": "text_start"}
    yield {"type": "text_chunk", "chunk": reply}
    yield {"type": "text_end"}
    yield {"type": "done", "success": True, "automation_id": automation_id}
