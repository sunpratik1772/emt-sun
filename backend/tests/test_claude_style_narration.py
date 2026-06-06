"""Claude-style Sherpa narration: thinking monologue + compact design reply."""
from __future__ import annotations

from copilot.build_narration import (
    assumption_close_line,
    build_thinking_monologue,
    pipeline_display_line,
)
from copilot.run_analyst import _deterministic_design_summary
from generation.harness.intent import classify
from tests.thinking_fake_adapter import ThinkingFakeAdapter


PROMPTS = [
    "Load leads.csv, filter high-risk rows, and export a CSV summary.",
    "Sort leads.csv by score descending and export to CSV.",
    "Load market_ticks, filter where spread_pips > 5, export CSV.",
    "Load leads.csv and accounts.csv, join on email, export matched leads.",
]


def _sample_workflow(name: str, nodes: list[dict]) -> dict:
    return {"name": name, "nodes": nodes, "edges": []}


def test_thinking_monologue_first_person_active_voice(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    intent = classify(PROMPTS[0], known_datasets={"leads.csv"})
    text = build_thinking_monologue(PROMPTS[0], intent, None, adapter=ThinkingFakeAdapter())
    lower = text.lower()
    assert "i'll" in lower or "examining" in lower or "auditing" in lower or "mapping" in lower
    assert "score" in lower or "high-risk" in lower
    assert "Drafting now." in text
    assert "maps to" not in lower
    assert "csv_output" not in lower
    assert "your prompt" not in lower


def test_thinking_monologue_varies_by_prompt(monkeypatch) -> None:
    monkeypatch.setattr("copilot.thinking_monologue.gemini_configured", lambda: True)
    outputs: list[str] = []
    for prompt in PROMPTS:
        intent = classify(prompt, known_datasets={"leads.csv", "market_ticks", "accounts.csv"})
        outputs.append(build_thinking_monologue(prompt, intent, None, adapter=ThinkingFakeAdapter()))
    assert len(set(outputs)) >= 3
    assert all("Drafting now." in o for o in outputs)


def test_design_summary_claude_format_leads_high_risk() -> None:
    workflow = _sample_workflow(
        "High-risk leads CSV export",
        [
            {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n2", "type": "csv_extract", "label": "Load", "config": {"source": "leads.csv"}},
            {"id": "n3", "type": "filter", "label": "Filter", "config": {"expression": "row.score >= 80"}},
            {"id": "n4", "type": "csv_output", "label": "Export", "config": {"filename": "high_risk_leads_summary.csv"}},
        ],
    )
    text = _deterministic_design_summary(workflow, PROMPTS[0])
    assert text.startswith("**High-risk leads CSV export**")
    assert "Here's what each step does:" in text
    assert "CSV Extract" in text
    assert "row.score >= 80" in text
    assert "`leads.csv` → `score ≥ 80` → `high_risk_leads_summary.csv`" in text
    assert "At a glance:" in text
    assert "Steps:" not in text
    assert "Why these choices" not in text
    assert "Built:" not in text


def test_design_summary_four_prompts() -> None:
    cases = [
        (
            PROMPTS[0],
            _sample_workflow(
                "High-risk leads CSV export",
                [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {"id": "n2", "type": "csv_extract", "label": "Load", "config": {"source": "leads.csv"}},
                    {"id": "n3", "type": "filter", "label": "Filter", "config": {"expression": "row.score >= 80"}},
                    {"id": "n4", "type": "csv_output", "label": "Export", "config": {"filename": "high_risk_leads_summary.csv"}},
                ],
            ),
        ),
        (
            PROMPTS[1],
            _sample_workflow(
                "Leads sorted by score",
                [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {"id": "n2", "type": "csv_extract", "label": "Load", "config": {"source": "leads.csv"}},
                    {"id": "n3", "type": "sort", "label": "Sort", "config": {"sortBy": "score", "order": "desc"}},
                    {"id": "n4", "type": "csv_output", "label": "Export", "config": {"filename": "leads_sorted.csv"}},
                ],
            ),
        ),
        (
            PROMPTS[2],
            _sample_workflow(
                "Wide spread ticks",
                [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {"id": "n2", "type": "db_query", "label": "Load", "config": {"source": "market_ticks"}},
                    {"id": "n3", "type": "filter", "label": "Filter", "config": {"expression": "row.spread_pips > 5"}},
                    {"id": "n4", "type": "csv_output", "label": "Export", "config": {"filename": "wide_spreads.csv"}},
                ],
            ),
        ),
        (
            PROMPTS[3],
            _sample_workflow(
                "Leads joined to accounts",
                [
                    {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
                    {"id": "n2", "type": "csv_extract", "label": "Load leads", "config": {"source": "leads.csv"}},
                    {"id": "n3", "type": "csv_extract", "label": "Load accounts", "config": {"source": "accounts.csv"}},
                    {"id": "n4", "type": "join", "label": "Join", "config": {"leftKey": "email", "rightKey": "email"}},
                    {"id": "n5", "type": "csv_output", "label": "Export", "config": {"filename": "matched_leads.csv"}},
                ],
            ),
        ),
    ]
    for prompt, workflow in cases:
        text = _deterministic_design_summary(workflow, prompt)
        assert text.startswith(f"**{workflow['name']}**")
        assert "→" in text
        assert "**Next step:**" in text
        assert "?" in text.split("**Next step:**")[-1]
        assert "Steps:" not in text
        assert "Why these choices" not in text
        pipeline = pipeline_display_line(workflow)
        assert pipeline in text


def test_assumption_close_only_when_interpreted() -> None:
    workflow = _sample_workflow(
        "Sorted leads",
        [
            {"id": "n1", "type": "manual_trigger", "label": "Start", "config": {}},
            {"id": "n2", "type": "csv_extract", "label": "Load", "config": {"source": "leads.csv"}},
            {"id": "n3", "type": "sort", "label": "Sort", "config": {"sortBy": "score", "order": "desc"}},
        ],
    )
    assert assumption_close_line(PROMPTS[1], workflow) == ""
