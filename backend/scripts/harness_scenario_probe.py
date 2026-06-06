#!/usr/bin/env python3
"""
Run Sherpa harness against studio-aligned prompts (routing + optional live Gemini).

Usage:
  cd backend && python3 scripts/harness_scenario_probe.py
  cd backend && python3 scripts/harness_scenario_probe.py --live
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from generation.harness.blueprint_router import select_blueprint
from generation.harness.enrichment import known_datasets
from generation.harness.intent import classify
from generation.validator_adapter import ValidatorAdapter
from tests.test_harness_prompt_scenarios import (
    STUDIO_SCENARIO_PROMPTS,
    _broken_branch_workflow,
)


def run_routing_probe() -> int:
    ds = known_datasets()
    print(f"Registry bundles: {len(ds)}")
    print("-" * 72)
    failures = 0
    for scenario in STUDIO_SCENARIO_PROMPTS:
        intent = classify(scenario.prompt, known_datasets=ds)
        decision = select_blueprint(scenario.prompt, intent)
        bp = decision.blueprint_id if decision else "(none)"
        ok = True
        if scenario.expect_blueprint and bp != scenario.expect_blueprint:
            ok = False
        for forbidden in scenario.expect_blueprint_not:
            if bp == forbidden:
                ok = False
        for artifact in scenario.expect_artifacts:
            if artifact not in intent.artifacts:
                ok = False
        for dataset in scenario.expect_datasets:
            if dataset not in intent.datasets:
                ok = False
        status = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {scenario.name}")
        print(f"       artifacts={list(intent.artifacts)} datasets={list(intent.datasets)} blueprint={bp}")
        if scenario.expect_blueprint and bp != scenario.expect_blueprint:
            print(f"       expected blueprint={scenario.expect_blueprint}")
    print("-" * 72)
    print(f"Routing probe: {len(STUDIO_SCENARIO_PROMPTS) - failures}/{len(STUDIO_SCENARIO_PROMPTS)} passed")
    return failures


def run_live_probe() -> int:
    from generation.harness.memory import MemoryManager
    from generation.harness.retriever import ContextRetriever
    from generation.harness.runner import AgentRunner
    from generation.planner import Planner
    from copilot.workflow_generator import WorkflowCopilot
    from llm import gemini_configured

    if not gemini_configured():
        print("GEMINI_API_KEY not configured — skipping live probe")
        return 1

    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="sherpa_probe_"))
    cp = WorkflowCopilot()
    cp._memory = MemoryManager(memory_dir=tmp / "memory")
    cp._retriever = ContextRetriever(memory=cp._memory)
    cp._runner = AgentRunner(
        planner=Planner(),
        prompt_builder=cp._prompt_builder,
        memory=cp._memory,
        retriever=cp._retriever,
    )
    cp._runner.runtime_smoke_enabled = False
    cp._runner.parallel_enabled = False

    turns = [
        (
            "create",
            "Join hs_alerts and market_ticks on alert_id, export to Excel AlertsMarketData.xlsx",
            None,
            None,
        ),
        (
            "edit",
            "Add filter spread_pips >= 80 and sort by spread_pips descending before export",
            "workflow",
            None,
        ),
        (
            "fix_injected",
            "Fix validation errors: condition node needs true/false branch handles on both csv outputs",
            "broken",
            "errors",
        ),
    ]

    workflow = None
    failures = 0
    print("Live harness probe (Gemini)")
    print("-" * 72)

    for label, prompt, wf_key, err_key in turns:
        print(f"\n>>> Turn [{label}]: {prompt[:80]}...")
        kwargs: dict = {"iterations": 2}
        if wf_key == "workflow" and workflow:
            kwargs["current_workflow"] = workflow
        elif wf_key == "broken":
            broken = _broken_branch_workflow()
            validation = ValidatorAdapter().validate(broken)
            kwargs["current_workflow"] = broken
            kwargs["recent_errors"] = validation["errors"]
            print(f"    Injected {len(validation['errors'])} validation error(s)")

        result = cp.generate_with_critic(prompt, **kwargs)
        ok = bool(result.get("success"))
        if not ok:
            failures += 1
        types = sorted({n.get("type") for n in (result.get("workflow") or {}).get("nodes", [])})
        fixes = result.get("auto_fixes_applied") or []
        print(f"    success={ok} nodes={len((result.get('workflow') or {}).get('nodes', []))} types={types}")
        if fixes:
            print(f"    auto_fixes={fixes[:3]}")
        if not ok and result.get("errors"):
            print(f"    errors={json.dumps(result['errors'][:2], indent=2)[:400]}")
        if not ok and result.get("error"):
            print(f"    error={str(result['error'])[:300]}")
        if ok and result.get("workflow"):
            workflow = result["workflow"]

    print("-" * 72)
    print(f"Live probe: {len(turns) - failures}/{len(turns)} turns succeeded")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Sherpa harness scenario probe")
    parser.add_argument("--live", action="store_true", help="Run live Gemini multi-turn probe")
    args = parser.parse_args()
    routing_failures = run_routing_probe()
    live_failures = 0
    if args.live:
        print()
        live_failures = run_live_probe()
    return 1 if (routing_failures or live_failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
