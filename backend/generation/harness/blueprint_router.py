"""
Heuristic blueprint routing for high-value workflow intents.

When a request strongly matches a vetted Studio demo topology, we attach:
  1) a workflow skeleton hint for the planner prompt, and
  2) an intelligent parallel subtask plan for pre-planning.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.demo_paths import demo_workflow_path

from .intent import Intent


@dataclass(frozen=True)
class ParallelSubtask:
    subagent_type: str
    description: str
    prompt: str


@dataclass(frozen=True)
class BlueprintDecision:
    blueprint_id: str
    title: str
    why: str
    workflow_path: Path | None = None
    workflow_skeleton: dict[str, Any] | None = None
    parallel_tasks: tuple[ParallelSubtask, ...] = field(default_factory=tuple)

    def compact_workflow(self) -> dict[str, Any]:
        if self.workflow_skeleton is not None:
            raw = self.workflow_skeleton
        elif self.workflow_path is not None and self.workflow_path.is_file():
            raw = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(
                f"Blueprint workflow missing for {self.blueprint_id}"
            )
        return {
            "workflow_id": raw.get("workflow_id"),
            "name": raw.get("name"),
            "description": raw.get("description"),
            "nodes": [
                {
                    "id": n.get("id"),
                    "type": n.get("type"),
                    "label": n.get("label"),
                    "config": n.get("config"),
                }
                for n in (raw.get("nodes") or [])
            ],
            "edges": [{"from": e.get("from"), "to": e.get("to")} for e in (raw.get("edges") or [])],
        }


def _blueprint(
    *,
    blueprint_id: str,
    title: str,
    filename: str,
    why: str,
    parallel_tasks: tuple[ParallelSubtask, ...] = (),
) -> BlueprintDecision | None:
    path = demo_workflow_path(filename)
    if not path.is_file():
        return None
    return BlueprintDecision(
        blueprint_id=blueprint_id,
        title=title,
        workflow_path=path,
        why=why,
        parallel_tasks=parallel_tasks,
    )


def _wants_spread_monitor(text: str, *, has_market_ticks: bool) -> bool:
    """Spread monitor blueprint — not join/filter follow-ups that mention spread_pips."""
    if not has_market_ticks:
        return False
    monitor_context = any(
        k in text
        for k in ("confluence", "monitor", "watch", "alert publish", "publish alert")
    )
    if "db_query" in text and ("monitor" in text or "watch" in text):
        monitor_context = True
    if not monitor_context:
        return False
    return (
        "spread_pips" in text
        or text.strip().startswith("spread")
        or " spread monitor" in text
        or "spread alert" in text
    )


def select_blueprint(scenario: str, intent: Intent) -> BlueprintDecision | None:
    text = (scenario or "").lower()
    has_hs_alerts = "hs_alerts" in text
    has_market_ticks = "market_ticks" in text or "market ticks" in text
    wants_publish = any(k in text for k in ("confluence", "jira", "mcp"))
    wants_spread_monitor = _wants_spread_monitor(text, has_market_ticks=has_market_ticks)

    # hs_alerts + market_ticks + publish — check before generic tick monitor
    if has_hs_alerts and has_market_ticks and wants_publish:
        return _blueprint(
            blueprint_id="alerts_ticks_join_publish",
            title="Alerts and ticks join with MCP publishing",
            filename="studio_14_alerts_ticks_join_publish.json",
            why="Detected joined alert/tick enrichment with publishing side-effects.",
            parallel_tasks=(
                ParallelSubtask(
                    subagent_type="explore",
                    description="Join contract check",
                    prompt="Verify join keys and field overlap between hs_alerts and market_ticks rows.",
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Risk threshold and shaping",
                    prompt="Design filter/map transforms for elevated spread risk digest rows.",
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Dual publish orchestration",
                    prompt="Sequence confluence_publish_report and jira_create_issue outputs for combined export.",
                ),
            ),
        )

    # db_query market tick spread monitoring -> conditional Confluence alerting
    if wants_spread_monitor:
        return _blueprint(
            blueprint_id="market_ticks_spread_monitor",
            title="Market spread monitor to Confluence",
            filename="studio_12_market_ticks_spread_monitor.json",
            why="Detected market tick spread monitoring + Confluence alert publish intent.",
            parallel_tasks=(
                ParallelSubtask(
                    subagent_type="explore",
                    description="Data access plan",
                    prompt=(
                        "Validate that market_ticks access should use db_query with SQL source inference "
                        "and identify required columns for spread monitoring."
                    ),
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Branch and alert logic",
                    prompt=(
                        "Draft branch semantics for spread threshold alerting and false-branch handling "
                        "with condition true/false outputs."
                    ),
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Confluence publish payload",
                    prompt=(
                        "Shape mcp confluence_publish_report params/data mapping for title/body_markdown/space "
                        "from alert rows."
                    ),
                ),
            ),
        )

    # Confluence action mining -> Jira backlog
    if ("confluence" in text and "action" in text) and ("jira" in text or "issue" in text):
        return _blueprint(
            blueprint_id="confluence_actions_to_jira",
            title="Confluence actions to Jira backlog",
            filename="studio_13_confluence_actions_issue_pipeline.json",
            why="Detected Confluence extraction + Jira issue orchestration intent.",
            parallel_tasks=(
                ParallelSubtask(
                    subagent_type="explore",
                    description="Confluence extraction flow",
                    prompt="Plan confluence_search_pages -> confluence_extract_action_items sequence and row schema.",
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Issue creation mapping",
                    prompt="Map extracted action rows to jira_create_issue payload and dedupe strategy.",
                ),
                ParallelSubtask(
                    subagent_type="general",
                    description="Backlog merge and export",
                    prompt="Plan merge of newly created and existing Jira issues with sorted export output.",
                ),
            ),
        )

    # Generic db_query monitor pattern
    if "db_query" in text and ("monitor" in text or "watch" in text):
        return _blueprint(
            blueprint_id="db_monitor_pattern",
            title="DB monitor condition publish pattern",
            filename="studio_12_market_ticks_spread_monitor.json",
            why="Detected generic db_query monitoring pattern; using vetted monitor topology.",
        )

    from engine.excel_blueprint import select_excel_blueprint

    if "leads.csv" in text or "leads.csv" in intent.datasets:
        from copilot.workflow_blueprints import (
            build_leads_filter_csv_skeleton,
            build_leads_sort_csv_skeleton,
        )

        if "sort" in text and ("csv" in text or "csv" in intent.artifacts):
            sk = build_leads_sort_csv_skeleton()
            return BlueprintDecision(
                blueprint_id="leads_sort_csv",
                title="Leads sort to CSV",
                why="Detected leads.csv sort + csv_output pattern.",
                workflow_skeleton=sk,
            )
        if any(k in text for k in ("filter", "high-risk", "high risk", "risk")):
            sk = build_leads_filter_csv_skeleton()
            return BlueprintDecision(
                blueprint_id="leads_filter_csv",
                title="High-risk leads CSV export",
                why="Detected leads.csv filter + csv export pattern.",
                workflow_skeleton=sk,
            )

    return select_excel_blueprint(scenario, intent)


def render_blueprint_hint(decision: BlueprintDecision | None) -> str:
    if decision is None:
        return ""
    try:
        compact = decision.compact_workflow()
    except FileNotFoundError:
        return ""
    return (
        "\n\n<recommended_blueprint>\n"
        f"id: {decision.blueprint_id}\n"
        f"title: {decision.title}\n"
        f"why: {decision.why}\n"
        "Use this as topology guidance; adapt details to user request while keeping the same execution pattern.\n"
        + json.dumps(compact, indent=2)[:7000]
        + "\n</recommended_blueprint>"
    )
