"""Tests for NL schedule parsing (LLM + heuristic)."""
from __future__ import annotations

import json

import pytest

from copilot.schedule_parser import (
    _parse_heuristic,
    _schedule_from_llm_payload,
    parse_schedule_from_text,
    wants_test_run,
)


class StubAdapter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def chat_turn(self, **kwargs):
        return json.dumps(self.payload)


def test_daily_morning_schedule():
    parsed = _parse_heuristic("run at 9:30 AM each morning")
    assert parsed.schedule_type == "cron"
    assert parsed.cron_expression == "30 9 * * *"
    assert "Daily" in parsed.summary


def test_weekday_schedule():
    parsed = _parse_heuristic("weekdays at 8:00 am")
    assert parsed.cron_expression == "0 8 * * 1-5"


def test_every_30_mins_for_12_hours_interval():
    msg = "save this as an automation that will run every 30 mins for next 12 jhours"
    parsed = _parse_heuristic(msg)
    assert parsed.schedule_type == "interval"
    assert parsed.interval_mins == 30
    assert parsed.duration_mins == 720
    assert "30" in parsed.summary
    assert "12" in parsed.summary
    assert "30:00" not in parsed.summary
    assert "Daily" not in parsed.summary


def test_every_30_mins_without_window_uses_cron():
    parsed = _parse_heuristic("run every 30 minutes")
    assert parsed.schedule_type == "cron"
    assert parsed.cron_expression == "*/30 * * * *"


def test_llm_interval_payload():
    parsed = _schedule_from_llm_payload(
        {
            "schedule_type": "interval",
            "cron_expression": "",
            "interval_mins": 30,
            "duration_mins": 720,
            "summary": "Every 30 minutes for 12 hours",
        }
    )
    assert parsed is not None
    assert parsed.schedule_type == "interval"
    assert parsed.interval_mins == 30
    assert parsed.duration_mins == 720
    assert parsed.source == "llm"


def test_llm_daily_cron_payload():
    parsed = _schedule_from_llm_payload(
        {
            "schedule_type": "cron",
            "cron_expression": "30 9 * * *",
            "interval_mins": None,
            "duration_mins": None,
            "summary": "Daily at 9:30 AM UTC",
        }
    )
    assert parsed is not None
    assert parsed.schedule_type == "cron"
    assert parsed.cron_expression == "30 9 * * *"


def test_llm_rejects_invalid_cron_hour():
    assert _schedule_from_llm_payload(
        {
            "schedule_type": "cron",
            "cron_expression": "0 30 * * *",
            "summary": "bad",
        }
    ) is None


def test_parse_schedule_uses_llm_when_configured(monkeypatch):
    monkeypatch.setattr("copilot.schedule_parser.gemini_configured", lambda: True)
    adapter = StubAdapter(
        {
            "schedule_type": "interval",
            "cron_expression": "",
            "interval_mins": 15,
            "duration_mins": 120,
            "summary": "Every 15 minutes for 2 hours",
        }
    )
    parsed = parse_schedule_from_text("automate every 15 mins for 2 hours", adapter=adapter)
    assert parsed.source == "llm"
    assert parsed.schedule_type == "interval"
    assert parsed.interval_mins == 15
    assert parsed.duration_mins == 120


def test_wants_test_run():
    assert wants_test_run("create automation and test it out")
    assert not wants_test_run("schedule only")
