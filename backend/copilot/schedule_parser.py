"""Natural-language schedule hints → cron or interval automations (LLM + heuristic)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from llm import GeminiAdapter, gemini_configured, get_default_adapter

_SCHEDULE_SYSTEM = """You parse automation schedule requests for dbSherpa Studio.

Return JSON only:
{
  "schedule_type": "cron" | "interval",
  "cron_expression": "minute hour day month weekday",
  "interval_mins": null or positive integer,
  "duration_mins": null or positive integer,
  "summary": "one short sentence describing the schedule in plain English"
}

All schedules run in UTC.

Rules:
- Use schedule_type=interval when the user wants repeated runs for a LIMITED time window
  (e.g. "every 30 minutes for the next 12 hours", "every 5 mins for 2 hours").
  Set interval_mins and duration_mins (convert hours to minutes).
- Use schedule_type=cron for open-ended calendar schedules:
  daily/weekly/weekday times, hourly, or "every N minutes" WITHOUT an end time.
- "every hour" → cron "0 * * * *"
- "every 5 minutes" (no end) → cron "*/5 * * * *"
- "daily at 9:30 AM" → cron "30 9 * * *"
- "weekdays at 8:00 AM" → cron "0 8 * * 1-5"
- NEVER treat "30 mins" in "every 30 mins" as clock time 30:00.
- Fix obvious typos (e.g. "jhours" → hours).
- cron_expression must be exactly 5 space-separated fields when schedule_type is cron.
- When schedule_type is interval, cron_expression may be empty string."""

_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

_INTERVAL_EVERY = re.compile(
    r"\bevery\s+(?P<n>\d+)\s*(?:min(?:ute)?s?)\b",
    re.IGNORECASE,
)
_DURATION_WINDOW = re.compile(
    r"(?:\b(?:for|next)\s+(?:the\s+)?)(?P<n>\d+)\s*j?\s*(?P<unit>hours?|hrs?|hr|minutes?|mins?|min)\b",
    re.IGNORECASE,
)
_CLOCK_COLON = re.compile(
    r"\b(?:at\s+)?(?P<hour>1?\d|2[0-3]):(?P<min>[0-5]\d)\b",
    re.IGNORECASE,
)
_CLOCK_AMPM = re.compile(
    r"\b(?P<hour>1?\d|2[0-3])(?::(?P<min>[0-5]\d))?\s*(?P<ampm>am|pm)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedSchedule:
    schedule_type: str  # "cron" | "interval"
    cron_expression: str
    summary: str
    interval_mins: int = 2
    duration_mins: int = 30
    timezone_note: str = "Schedules run in UTC."
    source: str = "heuristic"


def _extract_json(text: str) -> dict[str, Any] | None:
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


def _to_24h(hour: int, ampm: str | None) -> int:
    if ampm:
        am = ampm.lower() == "am"
        if hour == 12:
            return 0 if am else 12
        return hour if am else hour + 12
    return hour


def _duration_to_mins(n: int, unit: str) -> int:
    u = unit.lower().rstrip("s")
    if u in {"hour", "hr"}:
        return n * 60
    return n


def _parse_clock_time(lower: str) -> tuple[int, int] | None:
    m = _CLOCK_COLON.search(lower)
    if m:
        return int(m.group("hour")), int(m.group("min"))
    m = _CLOCK_AMPM.search(lower)
    if m:
        hour = _to_24h(int(m.group("hour")), m.group("ampm"))
        minute = int(m.group("min") or 0)
        return hour, minute
    return None


def _validate_cron(expr: str) -> bool:
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return False
    if parts[1].isdigit() and int(parts[1]) > 23:
        return False
    return True


def _schedule_from_llm_payload(payload: dict[str, Any]) -> ParsedSchedule | None:
    schedule_type = str(payload.get("schedule_type") or "cron").strip().lower()
    if schedule_type not in {"cron", "interval"}:
        schedule_type = "cron"

    summary = str(payload.get("summary") or "Scheduled automation").strip()[:240]
    interval_mins = max(1, int(payload.get("interval_mins") or 2))
    duration_mins = max(1, int(payload.get("duration_mins") or 30))
    cron = str(payload.get("cron_expression") or "").strip()

    if schedule_type == "interval":
        if interval_mins < 1 or duration_mins < 1:
            return None
        return ParsedSchedule(
            schedule_type="interval",
            cron_expression=cron or "0 * * * *",
            interval_mins=interval_mins,
            duration_mins=duration_mins,
            summary=summary,
            source="llm",
        )

    if not _validate_cron(cron):
        return None
    return ParsedSchedule(
        schedule_type="cron",
        cron_expression=cron,
        interval_mins=interval_mins,
        duration_mins=duration_mins,
        summary=summary,
        source="llm",
    )


def _parse_with_llm(text: str, adapter: GeminiAdapter) -> ParsedSchedule | None:
    user_turn = f"User automation request:\n{text.strip()}"
    raw = adapter.chat_turn(
        system_prompt=_SCHEDULE_SYSTEM,
        history=[],
        user_turn=user_turn,
        temperature=0.0,
        json_mode=True,
    )
    payload = _extract_json(raw) or {}
    return _schedule_from_llm_payload(payload)


def _parse_heuristic(text: str) -> ParsedSchedule:
    lower = (text or "").lower()

    every = _INTERVAL_EVERY.search(lower)
    window = _DURATION_WINDOW.search(lower)
    if every and window:
        interval_mins = max(1, int(every.group("n")))
        duration_mins = max(interval_mins, _duration_to_mins(int(window.group("n")), window.group("unit")))
        hours = duration_mins // 60
        if hours >= 1 and duration_mins % 60 == 0:
            dur_label = f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            dur_label = f"{duration_mins} minutes"
        return ParsedSchedule(
            schedule_type="interval",
            cron_expression="0 * * * *",
            interval_mins=interval_mins,
            duration_mins=duration_mins,
            summary=f"Every {interval_mins} minutes for {dur_label}",
            source="heuristic",
        )

    if re.search(r"\b(hourly|every hour)\b", lower):
        return ParsedSchedule("cron", "0 * * * *", "Runs hourly at minute 0", source="heuristic")

    every_mins = re.search(r"\bevery\s+(\d+)\s*(?:min(?:ute)?s?)\b", lower)
    if every_mins and not window:
        n = max(1, min(int(every_mins.group(1)), 59))
        return ParsedSchedule(
            schedule_type="cron",
            cron_expression=f"*/{n} * * * *",
            summary=f"Runs every {n} minutes",
            source="heuristic",
        )

    clock = _parse_clock_time(lower)
    hour, minute = clock if clock else (9, 0)
    day_of_week = "*"

    if re.search(r"\b(weekdays?|week day|monday through friday|mon-fri|mon thru fri)\b", lower):
        day_of_week = "1-5"
        summary = f"Weekdays at {hour:02d}:{minute:02d} UTC"
    elif re.search(r"\b(weekly|every week)\b", lower):
        day_of_week = "1"
        summary = f"Weekly on Monday at {hour:02d}:{minute:02d} UTC"
    elif re.search(r"\b(every 5 minutes|every five minutes)\b", lower):
        return ParsedSchedule("cron", "*/5 * * * *", "Runs every 5 minutes", source="heuristic")
    else:
        summary = f"Daily at {hour:02d}:{minute:02d} UTC"

    cron = f"{minute} {hour} * * {day_of_week}"
    return ParsedSchedule(
        schedule_type="cron",
        cron_expression=cron,
        summary=summary,
        source="heuristic",
    )


def parse_schedule_from_text(
    text: str,
    *,
    adapter: GeminiAdapter | None = None,
) -> ParsedSchedule:
    """Parse NL schedule — LLM when configured, heuristic fallback."""
    if gemini_configured():
        try:
            llm_schedule = _parse_with_llm(text, adapter or get_default_adapter())
            if llm_schedule is not None:
                return llm_schedule
        except Exception:
            pass
    return _parse_heuristic(text)


def wants_test_run(text: str) -> bool:
    lower = (text or "").lower()
    return bool(
        re.search(
            r"\b(test( it( out)?)?|try it( out)?|run it now|run now|trigger( it)?|smoke test)\b",
            lower,
        )
    )
