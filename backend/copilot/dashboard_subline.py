"""
LLM-generated dashboard welcome subline (one line under "Good morning, {name}").

The greeting line is composed in the frontend from time-of-day + user name.
This module only produces the second line: a short, workflow-focused question.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

# Four canonical welcome lines — workflow / getting started only (no product name, nodes, or platform Q&A).
GREETING_INSPIRATION_EXAMPLES: tuple[str, ...] = (
    "What would you like to build today?",
    "How can I help you get started on a workflow?",
    "What would you like to run or automate today?",
    "Ready to dive in — what's the goal for this session?",
)

FALLBACK_SUBLINES: tuple[str, ...] = GREETING_INSPIRATION_EXAMPLES

_INSPIRATION_BLOCK = "\n".join(f'  - "{line}"' for line in GREETING_INSPIRATION_EXAMPLES)

_SYSTEM_PROMPT = f"""You write exactly one short welcome subline for dbSherpa Studio's home screen.

Context:
- dbSherpa is a visual workflow studio: DAG editor, data steps, AI agent steps, MCP integrations, and a copilot that builds workflows from plain English.
- The user already sees a separate headline with their name and time of day (e.g. "Good morning, John"). Your line sits directly underneath.

Output JSON only, no markdown:
{{"subline": "<one line>"}}

Hardcoded inspiration examples (match this tone and intent; paraphrase freely — do NOT copy verbatim every time):
{_INSPIRATION_BLOCK}

Rules for subline:
- One line only: an inviting question or "let's start" phrase about workflows, automation, runs, or getting started in Studio.
- Prefer ending with "?". Occasional lines may end with "!" (e.g. "Let's get started — what should we build?").
- 6–18 words. Warm, action-oriented, about building/running/improving workflows.
- Do NOT use the product name "Sherpa" or "sherpa" in the subline (the brand is dbSherpa Studio; address the user directly with "I" or stay neutral).
- Do NOT mention node types, filtering, branching, palettes, APIs, JSON, or platform documentation-style questions.
- Do NOT repeat "Good morning/afternoon/evening" or the user's name unless it flows naturally (usually skip the name).
- No bullet lists, no quotes inside the string, no meta talk about AI or JSON.
"""


def generate_dashboard_subline(
    *,
    first_name: str = "",
    period: str = "",
) -> dict[str, Any]:
    """Return {subline, from_ai} for the dashboard welcome row."""
    ai_line = _generate_with_gemini(first_name=first_name.strip(), period=period.strip())
    if ai_line:
        return {"subline": ai_line, "from_ai": True}
    return {"subline": _pick_fallback(first_name), "from_ai": False}


def _pick_fallback(first_name: str) -> str:
    base = random.choice(FALLBACK_SUBLINES)
    if not first_name or first_name.lower() == "there":
        return base
    if random.random() < 0.25:
        return f"{first_name}, {base[0].lower()}{base[1:]}"
    return base


def _generate_with_gemini(*, first_name: str, period: str) -> str | None:
    try:
        from llm import gemini_configured, get_default_adapter

        if not gemini_configured():
            return None

        user_payload = {
            "task": "Write one fresh dashboard subline for this visit.",
            "first_name": first_name or "there",
            "time_of_day_period": period or "unknown",
            "product": "dbSherpa Studio — visual workflow editor + AI copilot",
            "inspiration_examples": list(GREETING_INSPIRATION_EXAMPLES),
        }
        raw = get_default_adapter().chat_turn(
            system_prompt=_SYSTEM_PROMPT,
            history=[],
            user_turn=json.dumps(user_payload, indent=2),
            temperature=0.9,
            json_mode=True,
        )
        return _coerce_subline(raw)
    except Exception:
        return None


def _coerce_subline(raw: str) -> str | None:
    try:
        payload = json.loads(_extract_json_object(raw))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    text = str(payload.get("subline") or "").strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    if len(text) > 120:
        text = text[:117].rstrip() + "…"
    if text.count("?") == 0 and text.count("!") == 0:
        text = f"{text}?"
    return text


def _extract_json_object(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return text[start : end + 1]
