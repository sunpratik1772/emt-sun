"""Live Gemini: five prompt types — route, thinking monologue, reply, Next step footer."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

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

_BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND / ".env")
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
                "query": (
                    "SELECT message_id, alert_id, participant_id, trader_name, "
                    "timestamp, relevance_score FROM comms_messages"
                ),
            },
        },
        {
            "id": "n04",
            "type": "join",
            "label": "Join",
            "config": {"leftKey": "alert_id", "rightKey": "alert_id", "joinType": "left"},
        },
        {
            "id": "n06",
            "type": "csv_output",
            "label": "CSV",
            "config": {"filename": "ranked_comms_alerts.csv"},
        },
    ],
    "edges": [{"from": "n01", "to": "n02"}, {"from": "n02", "to": "n04"}, {"from": "n04", "to": "n06"}],
}

_NEXT_STEP_RE = re.compile(r"\*\*Next step:\*\*", re.IGNORECASE)


def _gemini_configured() -> bool:
    try:
        from llm import gemini_configured

        return bool(gemini_configured())
    except Exception:
        key = os.environ.get("GEMINI_API_KEY", "")
        return bool(key) and key != "mock_key_for_testing"


def _run_log_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "node_id": "n02",
            "label": "Load Comms",
            "node_type": "db_query",
            "status": "ok",
            "duration_ms": 12,
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
        {
            "node_id": "n04",
            "label": "Join",
            "node_type": "join",
            "status": "ok",
            "duration_ms": 18,
            "output": {"node_output": {"rows": rows, "rowCount": len(rows)}},
        },
    ]


def _has_next_step(text: str) -> bool:
    action, question = parse_next_action_from_text(text)
    return bool(action and question and question.rstrip().endswith("?"))


def _thinking_preview(monologue: str, limit: int = 160) -> str:
    one_line = " / ".join(line.strip() for line in monologue.splitlines() if line.strip())
    return one_line[:limit] + ("…" if len(one_line) > limit else "")


@pytest.mark.integration
@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY not configured")
class TestSherpaFivePromptsLive:
    """One prompt per Sherpa route type; serial with rate-limit gaps."""

    @pytest.fixture(autouse=True)
    def _rate_limit_gap(self):
        time.sleep(14)
        yield

    @pytest.mark.parametrize("case", SHERPA_FIVE_PROMPT_CASES, ids=[c.case_id for c in SHERPA_FIVE_PROMPT_CASES])
    def test_five_prompt_live(self, case, capsys) -> None:
        ctx = dict(case.context)
        route = route_sherpa_message(case.message, **ctx)

        print(f"\n{'=' * 72}")
        print(f"CASE: {case.case_id} ({case.route_type})")
        print(f"PROMPT: {case.message[:100]}{'…' if len(case.message) > 100 else ''}")
        print(f"ROUTE: intent={route.intent!r} source={route.source!r}")
        print(f"REASON: {(route.reason or '')[:120]}")
        print(f"ENHANCED: {(route.enhanced_question or '')[:120]}")

        assert route.intent == case.expected_intent, (
            f"expected {case.expected_intent!r}, got {route.intent!r}: {route.reason}"
        )

        reply = ""
        monologue = ""

        if case.route_type == "build":
            intent = classify(case.message, known_datasets={"orders.csv"})
            monologue = build_thinking_monologue(case.message, intent, None)
            # Design-summary footer is deterministic after harness; validate monologue + route only here.
            print(f"THINKING: {_thinking_preview(monologue)}")
            assert "user wants" not in monologue.lower()
            assert "pipeline should work" not in monologue.lower()
            assert "Drafting" in monologue
            assert any(
                w in monologue for w in ("Examining", "Mapping", "I'll", "Auditing", "Tracing", "Checking")
            )

        elif case.route_type == "ask":
            monologue = build_ask_thinking_monologue(case.message)
            cp = WorkflowCopilot()
            raw = cp.chat(case.message, session_id=f"live-five-{case.case_id}")
            reply = ensure_ask_next_action_footer(raw, user_message=case.message)
            print(f"THINKING: {_thinking_preview(monologue)}")
            print(f"REPLY_PREVIEW: {reply[:280]}{'…' if len(reply) > 280 else ''}")
            assert _has_next_step(reply), "Ask reply missing **Next step:** + question"

        elif case.route_type == "explain_run":
            if not _FIXTURE_DB.is_file():
                pytest.skip("surveillance fixture missing")
            rows, _ = replay_workflow_rows(_COMMS_WORKFLOW)
            run_log = _run_log_rows(rows)
            monologue = build_run_review_monologue(
                route.enhanced_question or case.message,
                _COMMS_WORKFLOW,
                run_log,
                route_metadata=route.metadata,
            )
            chunks: list[str] = []
            reply = stream_run_execution_summary(
                _COMMS_WORKFLOW,
                run_log,
                None,
                chunks.append,
                user_message=route.enhanced_question or case.message,
                route_metadata=route.metadata,
            )
            print(f"THINKING: {_thinking_preview(monologue)}")
            print(f"REPLY_PREVIEW: {reply[:320]}{'…' if len(reply) > 320 else ''}")
            assert _has_next_step(reply), "Run review missing **Next step:** + question"
            assert _NEXT_STEP_RE.search(reply)

        elif case.route_type == "load":
            monologue = build_load_thinking_monologue(case.message, query="Join Comms")
            body = ensure_load_next_action_footer(
                "Loaded **Join Comms Messages with HS Alerts and Rank** (6 nodes) onto the canvas.",
                query="Join Comms",
                loaded_name="Join Comms Messages with HS Alerts and Rank",
                found=True,
            )
            reply = body
            print(f"THINKING: {_thinking_preview(monologue)}")
            print(f"REPLY_PREVIEW: {reply[:280]}")
            assert _has_next_step(reply)

        elif case.route_type == "automate":
            monologue = build_automate_thinking_monologue(
                case.message,
                workflow={"name": "Join Comms Messages with HS Alerts and Rank"},
                build_first=False,
            )
            reply = ensure_automate_next_action_footer(
                "Done — **Join Comms Automation** is scheduled: Weekdays at 9:30 AM.",
                automation_name="Join Comms Automation",
                schedule_summary="Weekdays at 9:30 AM",
            )
            print(f"THINKING: {_thinking_preview(monologue)}")
            print(f"REPLY_PREVIEW: {reply[:280]}")
            assert _has_next_step(reply)

        action, question = parse_next_action_from_text(reply) if reply else (None, None)
        if reply:
            print(f"NEXT_STEP: {action}")
            print(f"QUESTION: {question}")
