#!/usr/bin/env python3
"""Benchmark to compare agent generation accuracy/validation rates with vs. without UA context."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from generation.harness.runner import AgentRunner
from llm import gemini_configured

BENCHMARK_PROMPTS = [
    {
        "id": "scenario_auth_profile",
        "description": "User profile authentication workflow",
        "prompt": "Create a workflow that checks authentication status at /api/user/me and gets account details",
    },
    {
        "id": "scenario_database_csv",
        "description": "Extract hs_trades, filter by price, and output CSV",
        "prompt": "Load trades from hs_trades database, filter rows where price is above 150, and write to high_value_trades.csv",
    },
    {
        "id": "scenario_mcp_jira_confluence",
        "description": "Jira & Confluence MCP integration",
        "prompt": "Search Confluence pages, extract action items, and create Jira tickets for each item in the surveillance project",
    },
    {
        "id": "scenario_automation_schedule",
        "description": "Weekly cron scheduler",
        "prompt": "Create a workflow that runs every Monday at 9 AM, loads products, and outputs regional tab sheets in Excel",
    }
]


def run_test_case(runner: AgentRunner, prompt: str, enable_ua: bool) -> dict:
    # Set the toggle environment variable
    os.environ["DBSHERPA_ENABLE_UA_CONTEXT"] = "1" if enable_ua else "0"
    
    start_time = time.time()
    try:
        # Run workflow generation via runner
        state = runner.run(
            scenario=prompt,
            max_attempts=3,
        )
        duration = time.time() - start_time
        
        return {
            "success": state.is_valid,
            "attempts": state.attempts,
            "smoke_passed": state.runtime_smoke_passed,
            "errors": [e.get("message") for e in state.errors],
            "node_count": len(state.workflow.get("nodes", [])) if state.workflow else 0,
            "edge_count": len(state.workflow.get("edges", [])) if state.workflow else 0,
            "duration_s": round(duration, 2),
            "smoke_error": state.runtime_smoke_error,
        }
    except Exception as e:
        return {
            "success": False,
            "attempts": 0,
            "smoke_passed": False,
            "errors": [str(e)],
            "node_count": 0,
            "edge_count": 0,
            "duration_s": round(time.time() - start_time, 2),
            "smoke_error": str(e),
        }


def main() -> int:
    if not gemini_configured():
        print("GEMINI_API_KEY is not configured in environment/env files. Aborting.")
        return 1

    print("=" * 80)
    print("dbSherpa Copilot: Understand-Anything Context Benchmark")
    print("=" * 80)
    print("Comparing generation accuracy with vs. without codebase/flow context.")
    print()

    runner = AgentRunner()
    
    # We disable runtime smoke during benchmarks if they require external MCP server connectivity
    # that might not be running locally (to prevent blocking timeouts on creds).
    runner.runtime_smoke_enabled = False

    results = []

    for idx, tc in enumerate(BENCHMARK_PROMPTS):
        print(f"[{idx+1}/{len(BENCHMARK_PROMPTS)}] Prompt: '{tc['prompt']}'")
        print("  Running WITHOUT context...")
        res_without = run_test_case(runner, tc["prompt"], enable_ua=False)
        print(f"    -> Success: {res_without['success']} | Attempts: {res_without['attempts']} | Nodes: {res_without['node_count']} | Time: {res_without['duration_s']}s")
        
        # Pace LLM calls slightly to respect rate limits
        time.sleep(3)

        print("  Running WITH context...")
        res_with = run_test_case(runner, tc["prompt"], enable_ua=True)
        print(f"    -> Success: {res_with['success']} | Attempts: {res_with['attempts']} | Nodes: {res_with['node_count']} | Time: {res_with['duration_s']}s")
        print()

        results.append({
            "id": tc["id"],
            "prompt": tc["prompt"],
            "description": tc["description"],
            "without": res_without,
            "with": res_with,
        })
        
        time.sleep(5)

    # Output detailed report
    print("=" * 80)
    print("ACCURACY COMPARISON REPORT")
    print("=" * 80)
    print(f"{'Prompt ID':<25} | {'WITHOUT UA Context':<25} | {'WITH UA Context':<25}")
    print("-" * 80)
    
    total_without_success = 0
    total_with_success = 0
    
    for r in results:
        wo_status = "SUCCESS" if r["without"]["success"] else "FAILED"
        w_status = "SUCCESS" if r["with"]["success"] else "FAILED"
        
        wo_info = f"{wo_status} (Attempts: {r['without']['attempts']})"
        w_info = f"{w_status} (Attempts: {r['with']['attempts']})"
        
        if r["without"]["success"]:
            total_without_success += 1
        if r["with"]["success"]:
            total_with_success += 1
            
        print(f"{r['id']:<25} | {wo_info:<25} | {w_info:<25}")

    print("-" * 80)
    print(f"{'TOTAL SUCCESSES':<25} | {total_without_success}/{len(BENCHMARK_PROMPTS):<25} | {total_with_success}/{len(BENCHMARK_PROMPTS):<25}")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
