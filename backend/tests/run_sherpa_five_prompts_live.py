#!/usr/bin/env python3
"""Run the five-prompt Sherpa live suite and print a human-readable report."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from copilot.build_narration import (
    build_ask_thinking_monologue,
    build_automate_thinking_monologue,
    build_load_thinking_monologue,
    build_run_review_monologue,
    build_thinking_monologue,
)
from copilot.llm_router import route_sherpa_message
from copilot.next_action import (
    ensure_automate_next_action_footer,
    ensure_ask_next_action_footer,
    ensure_load_next_action_footer,
    parse_next_action_from_text,
)
from copilot.run_analyst import stream_run_execution_summary
from copilot.run_dataset_memory import replay_workflow_rows
from copilot.workflow_generator import WorkflowCopilot
from generation.harness.intent import classify
from tests.sherpa_five_prompt_cases import SHERPA_FIVE_PROMPT_CASES

_FIXTURE_DB = _BACKEND / "demo_data" / "surveillance_fixture.sqlite"

_COMMS_WORKFLOW = {
    "name": "Join Comms Messages with Alerts and Rank",
    "nodes": [
        {"id": "n01", "type": "manual_trigger", "label": "Start"},
        {
            "id": "n02",
            "type": "db_query",
            "label": "Load Comms",
            "config": {
                "source": "comms_messages",
                "query": "SELECT message_id, alert_id, trader_name, relevance_score FROM comms_messages",
            },
        },
        {
            "id": "n04",
            "type": "join",
            "label": "Join",
            "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
        },
        {"id": "n06", "type": "csv_output", "label": "CSV", "config": {"filename": "ranked.csv"}},
    ],
    "edges": [{"from": "n01", "to": "n02"}, {"from": "n02", "to": "n04"}, {"from": "n04", "to": "n06"}],
}


def _run_log(rows: list[dict]) -> list[dict]:
    return [
        {
            "node_id": "n02",
            "label": "Load Comms",
            "node_type": "db_query",
            "status": "ok",
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
        {
            "node_id": "n04",
            "label": "Join",
            "node_type": "join",
            "status": "ok",
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
    ]


def main() -> int:
    from llm import gemini_configured

    if not gemini_configured():
        print("GEMINI_API_KEY not configured — aborting.")
        return 1

    print("Sherpa five-prompt live report (Gemini)\n")

    for i, case in enumerate(SHERPA_FIVE_PROMPT_CASES):
        if i:
            time.sleep(14)
        print("=" * 72)
        print(f"{case.case_id}  [{case.route_type}]")
        print(f"Prompt: {case.message}")
        print()

        route = route_sherpa_message(case.message, **case.context)
        print(f"Router → intent={route.intent!r}  source={route.source!r}")
        print(f"Reason: {route.reason}")
        if route.enhanced_question and route.enhanced_question != case.message:
            print(f"Enhanced: {route.enhanced_question[:200]}")

        reply = ""
        if case.route_type == "build":
            intent = classify(case.message, known_datasets={"orders.csv"})
            mono = build_thinking_monologue(case.message, intent, None)
            print(f"\nThinking monologue:\n{mono}")
            print("\n(Build reply comes from harness after this — not run in this quick suite.)")

        elif case.route_type == "ask":
            mono = build_ask_thinking_monologue(case.message)
            print(f"\nThinking monologue:\n{mono}")
            cp = WorkflowCopilot()
            raw = cp.chat(case.message, session_id=f"report-{case.case_id}")
            reply = ensure_ask_next_action_footer(raw, user_message=case.message)
            print(f"\nReply (first 500 chars):\n{reply[:500]}")

        elif case.route_type == "explain_run":
            if not _FIXTURE_DB.is_file():
                print("Fixture DB missing — skip")
                continue
            rows, _ = replay_workflow_rows(_COMMS_WORKFLOW)
            log = _run_log(rows)
            mono = build_run_review_monologue(
                route.enhanced_question or case.message,
                _COMMS_WORKFLOW,
                log,
                route_metadata=route.metadata,
            )
            print(f"\nThinking monologue:\n{mono}")
            reply = stream_run_execution_summary(
                _COMMS_WORKFLOW,
                log,
                None,
                lambda _: None,
                user_message=route.enhanced_question or case.message,
                route_metadata=route.metadata,
            )
            print(f"\nReply (first 600 chars):\n{reply[:600]}")

        elif case.route_type == "load":
            mono = build_load_thinking_monologue(case.message, query="Join Comms")
            print(f"\nThinking monologue:\n{mono}")
            reply = ensure_load_next_action_footer(
                "Loaded **Join Comms Messages with HS Alerts and Rank** (6 nodes) onto the canvas.",
                query="Join Comms",
                loaded_name="Join Comms Messages with HS Alerts and Rank",
                found=True,
            )
            print(f"\nReply:\n{reply}")

        elif case.route_type == "automate":
            mono = build_automate_thinking_monologue(
                case.message,
                workflow={"name": "Join Comms Messages with HS Alerts and Rank"},
            )
            print(f"\nThinking monologue:\n{mono}")
            reply = ensure_automate_next_action_footer(
                "Done — **Join Comms Automation** is scheduled: Weekdays at 9:30 AM.",
                automation_name="Join Comms Automation",
                schedule_summary="Weekdays at 9:30 AM",
            )
            print(f"\nReply:\n{reply}")

        action, question = parse_next_action_from_text(reply) if reply else (None, None)
        if action:
            print(f"\nNext step action: {action}")
            print(f"Closing question: {question}")
        print()

    print("Done — 5/5 cases processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
