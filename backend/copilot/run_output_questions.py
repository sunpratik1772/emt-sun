"""Detect when the user is asking about workflow run output (not platform Q&A)."""
from __future__ import annotations

import re

_RUN_OUTPUT_QUESTION = re.compile(
    r"\b("
    r"analy[sz]e|describe|explain|summari[sz]e|review|walk me through|tell me about"
    r"|what happened|what was the output|what did it produce|what did the run"
    r"|how many rows|row count|show me the (results?|output|data)"
    r"|top\s+\d+|who are the|which trader|name.*trader"
    r"|output of|results of|run summary|execution summary"
    r"|latest run|last run|reliability|suggest.*change"
    r")\b",
    re.IGNORECASE,
)

_BUILD_OVERRIDE = re.compile(
    r"\b("
    r"build|create|generate|fix|repair|improve|wire|connect|extend|also add|add a|add node"
    r"|remove node|edit workflow|github_mcp|confluence_mcp|jira_mcp|publish|agent node|use github"
    r")\b",
    re.IGNORECASE,
)


def is_run_output_question(text: str) -> bool:
    """True when the message is about interpreting a completed run."""
    scenario = (text or "").strip()
    if not scenario:
        return False
    if _BUILD_OVERRIDE.search(scenario):
        return False
    return bool(_RUN_OUTPUT_QUESTION.search(scenario))
