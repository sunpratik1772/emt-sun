"""
Intent classification for agent requests.

Extracts structured intent from a user's natural-language scenario so
downstream modules (retriever, template selector, prompt builder) can
make informed decisions about what context to load.

Intent signals:
  - mode:       "create" or "edit" (is there an existing workflow?)
  - scenarios:  domain keywords (e.g. "front-running", "spoofing")
  - datasets:   referenced data sources (e.g. "orders", "trades")
  - actions:    what the user wants (e.g. "add", "remove", "fix", "merge")
  - artifacts:  requested outputs (e.g. "csv", "excel", "email")
  - node_types: explicitly mentioned node types (e.g. "code", "agent", "mcp")

No LLM needed — this is fast keyword extraction. The LLM gets the raw
scenario anyway; intent is a routing signal for the harness, not a
replacement for understanding.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_SCENARIO_KEYWORDS = {
    "front-running", "front running", "fro",
    "spoofing", "layering",
    "wash trading", "wash-trading",
    "insider trading", "insider-trading",
    "market manipulation",
    "surveillance", "alert", "compliance",
    "benchmark", "fixing",
    "ramp and dump", "pump and dump",
}

_ACTION_KEYWORDS = {
    "create": {"create", "build", "generate", "make", "new", "design"},
    "add": {"add", "insert", "include", "append"},
    "remove": {"remove", "delete", "drop", "strip"},
    "fix": {"fix", "repair", "correct", "resolve", "debug"},
    "edit": {"edit", "change", "modify", "update", "adjust", "tweak"},
    "merge": {"merge", "combine", "join", "union"},
    "split": {"split", "branch", "route", "fork"},
    "filter": {"filter", "where", "exclude", "only"},
    "sort": {"sort", "order", "rank", "descending", "ascending"},
    "aggregate": {"aggregate", "group", "summarize", "count", "sum", "average"},
}

_ARTIFACT_KEYWORDS = {
    "csv": {"csv"},
    "excel": {"excel", "xlsx", "spreadsheet"},
    "json": {"json"},
    "markdown": {"markdown", "md", "report"},
    "email": {"email", "mail", "send"},
    "pdf": {"pdf"},
    "file": {"file", "output", "export", "artifact", "download"},
}


@dataclass(frozen=True)
class Intent:
    mode: str                               # "create" | "edit"
    scenarios: tuple[str, ...]              # domain keywords found
    datasets: tuple[str, ...]               # data sources referenced
    actions: tuple[str, ...]                # user intent verbs
    artifacts: tuple[str, ...]              # requested output types
    node_types: tuple[str, ...]             # explicitly named node types
    raw_scenario: str = ""                  # original text

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "scenarios": list(self.scenarios),
            "datasets": list(self.datasets),
            "actions": list(self.actions),
            "artifacts": list(self.artifacts),
            "node_types": list(self.node_types),
        }


def classify(
    scenario: str,
    current_workflow: dict | None = None,
    known_datasets: set[str] | None = None,
    known_node_types: set[str] | None = None,
) -> Intent:
    """Extract structured intent from a scenario string.

    Pure function, no side effects, no LLM. Fast enough to call on
    every request.
    """
    lower = scenario.lower()
    tokens = set(re.findall(r"[a-z][a-z0-9_-]+", lower))

    mode = "edit" if current_workflow is not None else "create"

    scenarios = tuple(sorted(
        kw for kw in _SCENARIO_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", lower)
    ))

    actions = tuple(sorted(
        action for action, synonyms in _ACTION_KEYWORDS.items()
        if tokens & synonyms
    ))

    artifacts = tuple(sorted(
        fmt for fmt, synonyms in _ARTIFACT_KEYWORDS.items()
        if tokens & synonyms
    ))

    # Match dataset names from the live registry
    datasets: list[str] = []
    if known_datasets:
        for ds in known_datasets:
            ds_lower = ds.lower().replace("_", " ")
            if ds_lower in lower or ds.lower() in tokens:
                datasets.append(ds)
    datasets_tuple = tuple(sorted(datasets))

    # Match node types mentioned explicitly (e.g. "csv_output node", "CODE")
    node_types: list[str] = []
    upper_tokens = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", scenario))
    lower_text = lower
    if known_node_types:
        for nt in known_node_types:
            nt_lower = nt.lower()
            if nt in upper_tokens or re.search(rf"\b{re.escape(nt_lower)}\b", lower_text):
                node_types.append(nt)
    node_types_tuple = tuple(sorted(node_types))

    return Intent(
        mode=mode,
        scenarios=scenarios,
        datasets=datasets_tuple,
        actions=actions,
        artifacts=artifacts,
        node_types=node_types_tuple,
        raw_scenario=scenario,
    )


_BUILD_COMMAND = re.compile(
    r"\b(create|generate|build|make|design|draft)\b.{0,40}\b(workflow|pipeline|automation|dag)\b"
    r"|\b(fix|repair|add node|remove node|update workflow|change this node)\b"
    r"|\b(csv_extract|csv_output|excel_output|db_query|manual_trigger|filter|join|group_by|map_transform|jira_mcp|confluence_mcp|github_mcp|github)\b"
    r"|\b(use|using)\s+['\"][a-z0-9_.-]+['\"]"
    r"|\b(use|using)\s+(the\s+)?(csv_extract|csv_output|excel_output|db_query|manual_trigger|filter|join|group_by|map_transform|jira_mcp|confluence_mcp|github_mcp|github)\b",
    re.IGNORECASE,
)

_ADVISORY_QUESTION = re.compile(
    r"\?"
    r"|\b(what|how|why|explain|tell me|help me understand|show me|list)\b"
    r"|\b(what are my options|what should i|how do i|how can i|what can i|options to get|ways to fix)\b"
    r"|\b(what went wrong|why did|is it possible|so tell me|walk me through|help me with)\b",
    re.IGNORECASE,
)

_RESOURCE_QUESTION = re.compile(
    r"\b(available|what are the|what's available|which)\b.{0,40}\b(skills?|nodes?|data sources?|integrations?|datasets?)\b"
    r"|\b(skills?|nodes?|data sources?|integrations?)\b.{0,30}\b(available|do you have|can i use)\b",
    re.IGNORECASE,
)

_RECOVERY_QUESTION = re.compile(
    r"\b(options|fix|work|recover|next step|what now|get it to work|make it work)\b",
    re.IGNORECASE,
)


def is_advisory_question_heuristic(
    text: str,
    *,
    recent_errors: list[dict] | None = None,
) -> bool:
    """Regex fallback when LLM intent routing is unavailable."""
    scenario = (text or "").strip()
    if not scenario:
        return False
    try:
        from copilot.run_output_questions import is_run_output_question

        if is_run_output_question(scenario):
            return False
    except Exception:
        pass
    if _RESOURCE_QUESTION.search(scenario):
        return True
    if _BUILD_COMMAND.search(scenario):
        return False
    if _ADVISORY_QUESTION.search(scenario):
        return True
    if recent_errors and _RECOVERY_QUESTION.search(scenario):
        return True
    return False


def is_advisory_question(
    text: str,
    *,
    recent_errors: list[dict] | None = None,
) -> bool:
    """LLM intent routing with heuristic fallback."""
    from copilot.intent_router import classify_copilot_intent

    return (
        classify_copilot_intent(text, recent_errors=recent_errors).intent == "ask"
    )
