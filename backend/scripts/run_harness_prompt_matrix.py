#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

RESULTS_PATH = ROOT / "scripts" / "harness_prompt_matrix_results.json"
SUMMARY_JSON_PATH = ROOT / "scripts" / "harness_prompt_matrix_summary.json"
SUMMARY_MD_PATH = ROOT / "scripts" / "harness_prompt_matrix_summary.md"

COMPLEXITY_ORDER: tuple[str, ...] = (
    "comms_github",
    "product_join",
    "regional_branch",
    "merge_workforce",
    "mcp_trio",
)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    complexity: int
    explicit_prompt: str
    nl_prompt: str
    check_fn: Callable[[dict], tuple[bool, str, str]]


def _types(wf: dict) -> list[str]:
    return [str(n.get("type", "")).lower() for n in wf.get("nodes", [])]


def _config_blob(wf: dict) -> str:
    return json.dumps([n.get("config", {}) for n in wf.get("nodes", [])]).lower()


def _has_any(items: list[str], *targets: str) -> bool:
    s = set(items)
    return any(t in s for t in targets)


def check_comms_github(wf: dict) -> tuple[bool, str, str]:
    types = _types(wf)
    blob = _config_blob(wf)
    retrieval_ok = ("comms_messages" in blob) and _has_any(types, "csv_extract", "db_query")
    triage_ok = _has_any(types, "filter", "code")
    issue_ok = _has_any(types, "github", "mcp")
    if retrieval_ok and triage_ok and issue_ok:
        return True, "ok", "retrieval+triage+issue capability satisfied"
    if not retrieval_ok:
        return False, "missing_retrieval_capability", "needs comms dataset retrieval capability"
    if not triage_ok:
        return False, "missing_triage_capability", "needs urgent-message triage capability"
    return False, "missing_issue_creation_capability", "needs issue creation capability"


def check_product_join(wf: dict) -> tuple[bool, str, str]:
    types = _types(wf)
    blob = _config_blob(wf)
    retrieval_ok = "orders.csv" in blob and "products.csv" in blob
    combine_ok = _has_any(types, "join", "data_merge")
    transform_ok = _has_any(types, "map_transform", "code")
    output_ok = _has_any(types, "csv_output", "excel_output")
    if retrieval_ok and combine_ok and transform_ok and output_ok:
        return True, "ok", "retrieval+combine+transform+output capability satisfied"
    if not retrieval_ok:
        return False, "missing_dual_dataset_retrieval", "orders and products datasets not both present"
    if not combine_ok:
        return False, "missing_combine_capability", "missing combine capability"
    if not transform_ok:
        return False, "missing_transform_capability", "missing line_total transform capability"
    return False, "missing_output_capability", "missing file output capability"


def check_regional_branch(wf: dict) -> tuple[bool, str, str]:
    types = _types(wf)
    blob = _config_blob(wf)
    retrieval_ok = "leads.csv" in blob
    branch_ok = _has_any(types, "router", "condition", "switch", "filter")
    output_ok = _has_any(types, "csv_output", "excel_output")
    if retrieval_ok and branch_ok and output_ok:
        return True, "ok", "retrieval+branch+output capability satisfied"
    if not retrieval_ok:
        return False, "missing_retrieval_capability", "leads retrieval missing"
    if not branch_ok:
        return False, "missing_branching_capability", "branching capability missing"
    return False, "missing_output_capability", "file output missing"


def check_merge_workforce(wf: dict) -> tuple[bool, str, str]:
    types = _types(wf)
    blob = _config_blob(wf)
    retrieval_ok = ("orders.csv" in blob) and ("employees.csv" in blob)
    merge_ok = _has_any(types, "data_merge", "join", "map_transform")
    summarize_ok = _has_any(types, "group_by", "agent", "code")
    output_ok = _has_any(types, "csv_output", "excel_output")
    if retrieval_ok and merge_ok and summarize_ok and output_ok:
        return True, "ok", "retrieval+merge+summary+output capability satisfied"
    if not retrieval_ok:
        return False, "missing_dual_dataset_retrieval", "orders/employees retrieval not both present"
    if not merge_ok:
        return False, "missing_merge_capability", "merge/combine capability missing"
    if not summarize_ok:
        return False, "missing_summary_capability", "region summary capability missing"
    return False, "missing_output_capability", "output capability missing"


def check_mcp_trio(wf: dict) -> tuple[bool, str, str]:
    types = _types(wf)
    mcp_nodes = [n for n in wf.get("nodes", []) if str(n.get("type", "")).lower() == "mcp"]
    integrations = {
        str((n.get("config") or {}).get("integration", "")).lower()
        for n in mcp_nodes
    }
    integration_ok = {"atlassian", "github"}.issubset(integrations)
    merge_ok = _has_any(types, "data_merge", "join", "agent")
    output_ok = _has_any(types, "csv_output", "excel_output")
    if integration_ok and merge_ok and output_ok:
        return True, "ok", "integration+merge+output capability satisfied"
    if not integration_ok:
        return False, "integration_pair_mismatch", f"integrations present: {sorted(integrations)}"
    if not merge_ok:
        return False, "missing_merge_capability", "merge/synthesis capability missing"
    return False, "missing_output_capability", "output capability missing"


SCENARIOS: dict[str, Scenario] = {
    "comms_github": Scenario(
        id="comms_github",
        title="Urgent comms → GitHub",
        complexity=1,
        explicit_prompt=(
            "Read records from the comms_messages dataset, keep rows where display_post "
            "contains 'urgent', and create one tracker issue per matching message."
        ),
        nl_prompt=(
            "Find surveillance chat messages whose body text mentions 'urgent' and "
            "open a tracker issue for each match."
        ),
        check_fn=check_comms_github,
    ),
    "product_join": Scenario(
        id="product_join",
        title="Orders × products join",
        complexity=2,
        explicit_prompt=(
            "Create a flow that combines orders.csv with products.csv on SKU, computes "
            "line_total as quantity multiplied by unit_price, ranks by highest line_total, "
            "and exports the result to CSV."
        ),
        nl_prompt=(
            "Combine order lines with the product catalog on SKU, calculate each "
            "line's revenue, rank highest first, and export a CSV report."
        ),
        check_fn=check_product_join,
    ),
    "regional_branch": Scenario(
        id="regional_branch",
        title="Lead region split",
        complexity=3,
        explicit_prompt=(
            "Load leads.csv, split the records by region into separate branches, and "
            "export one file per major region."
        ),
        nl_prompt=(
            "Load the lead list and split it by sales region into separate export files."
        ),
        check_fn=check_regional_branch,
    ),
    "merge_workforce": Scenario(
        id="merge_workforce",
        title="Orders + employees merge",
        complexity=4,
        explicit_prompt=(
            "Combine orders.csv with employees.csv into one stream, summarize total order "
            "value by region, rank regions from highest to lowest total, and export to CSV."
        ),
        nl_prompt=(
            "Merge order revenue with employee headcount data, summarize total order "
            "value by region, and save the summary as CSV."
        ),
        check_fn=check_merge_workforce,
    ),
    "mcp_trio": Scenario(
        id="mcp_trio",
        title="Atlassian + GitHub MCP integrations",
        complexity=5,
        explicit_prompt=(
            "Fetch sample company data from a public API, keep the top five rows, search "
            "Confluence content, publish a short report to Atlassian, trigger an engineering "
            "follow-up task, combine all outcomes, write an executive briefing, and export CSV."
        ),
        nl_prompt=(
            "Pull sample companies from a public API, search Confluence, publish a "
            "short report to Atlassian, log an engineering follow-up, merge the results, "
            "write an executive briefing, and export CSV."
        ),
        check_fn=check_mcp_trio,
    ),
}

STYLE_ALIASES = {"physical": "physical", "explicit": "physical", "logical": "logical", "nl": "logical"}


def _run_prompt(copilot, prompt: str, *, label: str) -> dict:
    print(f"\n{'─' * 72}\n[{label}]\n{prompt}\n")
    events: list[dict] = []
    start = time.perf_counter()
    for frame in copilot.generate_with_critic_stream(prompt, iterations=3):
        events.append(frame)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    done = next((e for e in reversed(events) if e.get("type") == "done"), None)
    wf_events = [e for e in events if e.get("type") == "workflow_created"]
    wf = (wf_events[-1].get("workflow") if wf_events else None) or {}
    success = bool(done and done.get("success"))
    types = _types(wf)
    if types:
        print("  nodes:", " → ".join(types))
    print(f"  done: success={success} runtime_ms={elapsed_ms}")
    return {"success": success, "workflow": wf, "types": types, "runtime_ms": elapsed_ms}


def _evaluate(scenario: Scenario, style: str, row: dict, *, episode: int) -> dict:
    check_ok, reason_code, detail = scenario.check_fn(row["workflow"])
    passed = row["success"] and check_ok
    return {
        "scenario": scenario.id,
        "title": scenario.title,
        "complexity": scenario.complexity,
        "style": style,
        "episode": episode,
        "prompt_mode": "physical (structured NL)" if style == "physical" else "logical (NL only)",
        "passed": passed,
        "success": row["success"],
        "types": row["types"],
        "check_ok": check_ok,
        "failure_reason": "ok" if passed else reason_code,
        "check_detail": detail,
        "workflow_name": (row["workflow"] or {}).get("name"),
        "node_count": len(row["types"]),
        "runtime_ms": row["runtime_ms"],
    }


def _run_one(copilot, scenario_id: str, style: str, *, episode: int) -> dict:
    scenario = SCENARIOS[scenario_id]
    prompt = scenario.explicit_prompt if style == "physical" else scenario.nl_prompt
    label = f"#{scenario.complexity} {scenario.id} / {style} / ep{episode}"
    row = _run_prompt(copilot, prompt, label=label)
    result = _evaluate(scenario, style, row, episode=episode)
    mark = "PASS" if result["passed"] else "FAIL"
    print(
        f"  => {mark} harness={result['success']} capability={result['check_ok']} "
        f"reason={result['failure_reason']}"
    )
    if not result["check_ok"]:
        print(f"     {result['check_detail']}")
    return result


def _aggregate(results: list[dict]) -> dict:
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        groups.setdefault((r["scenario"], r["style"]), []).append(r)

    summary_rows: list[dict] = []
    for (scenario, style), rows in sorted(groups.items()):
        pass_rate = sum(1 for r in rows if r["passed"]) / len(rows)
        node_counts = [r["node_count"] for r in rows]
        runtimes = [r["runtime_ms"] for r in rows]
        failure_reasons = [r["failure_reason"] for r in rows if r["failure_reason"] != "ok"]
        dominant_reason = "ok"
        if failure_reasons:
            dominant_reason = max(set(failure_reasons), key=failure_reasons.count)
        summary_rows.append(
            {
                "scenario": scenario,
                "style": style,
                "episodes": len(rows),
                "pass_rate": round(pass_rate, 4),
                "variance": round(statistics.pvariance([1 if r["passed"] else 0 for r in rows]), 6),
                "avg_runtime_ms": round(sum(runtimes) / len(runtimes), 2),
                "avg_node_count": round(sum(node_counts) / len(node_counts), 2),
                "dominant_failure_reason": dominant_reason,
            }
        )

    overall_pass_rate = sum(1 for r in results if r["passed"]) / max(1, len(results))
    overall_runtime = round(sum(r["runtime_ms"] for r in results) / max(1, len(results)), 2)
    return {"overall_pass_rate": round(overall_pass_rate, 4), "overall_avg_runtime_ms": overall_runtime, "summary": summary_rows}


def _write_md_report(path: Path, aggregate: dict) -> None:
    lines = [
        "# Harness Prompt Matrix Summary",
        "",
        f"- overall_pass_rate: {aggregate['overall_pass_rate']}",
        f"- overall_avg_runtime_ms: {aggregate['overall_avg_runtime_ms']}",
        "",
        "## Scenario/Style Summary",
    ]
    for row in aggregate["summary"]:
        lines.append(
            f"- {row['scenario']} / {row['style']}: pass_rate={row['pass_rate']} "
            f"variance={row['variance']} avg_runtime_ms={row['avg_runtime_ms']} "
            f"dominant_failure_reason={row['dominant_failure_reason']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_list() -> None:
    print("Complexity order (low → high):")
    for i, sid in enumerate(COMPLEXITY_ORDER, start=1):
        s = SCENARIOS[sid]
        print(f"  {i}. {sid:18} — {s.title}")
    print("\nPrompts are natural-language only (no node-name requirements).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequential harness prompt matrix")
    parser.add_argument("--list", action="store_true", help="Show complexity order")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()))
    parser.add_argument("--style", choices=["physical", "logical", "both"])
    parser.add_argument("--all", action="store_true", help="Run all scenario/style pairs")
    parser.add_argument("--episodes", type=int, default=3, help="Episodes per scenario/style")
    parser.add_argument("--output-json", type=str, default=str(SUMMARY_JSON_PATH), help="Aggregate JSON output path")
    parser.add_argument("--output-md", type=str, default=str(SUMMARY_MD_PATH), help="Aggregate markdown output path")
    parser.add_argument("--no-smoke", action="store_true", help="Skip runtime smoke")
    args = parser.parse_args()

    if args.list:
        _print_list()
        return 0

    from llm import gemini_configured
    from copilot.workflow_generator import WorkflowCopilot

    if not gemini_configured():
        print("ERROR: GEMINI_API_KEY not configured in backend/.env")
        return 1

    if not args.scenario and not args.all:
        parser.print_help()
        return 1

    copilot = WorkflowCopilot()
    copilot._runner.runtime_smoke_enabled = not args.no_smoke
    episodes = max(1, int(args.episodes))
    results: list[dict] = []

    if args.all:
        for sid in COMPLEXITY_ORDER:
            for style in ("physical", "logical"):
                for ep in range(1, episodes + 1):
                    print(f"\n{'=' * 72}\nRunning {sid} / {style} / episode {ep}\n{'=' * 72}")
                    results.append(_run_one(copilot, sid, style, episode=ep))
    else:
        style = STYLE_ALIASES.get(args.style or "physical", args.style or "physical")
        styles = ("physical", "logical") if style == "both" else (style,)
        for st in styles:
            for ep in range(1, episodes + 1):
                results.append(_run_one(copilot, args.scenario, st, episode=ep))

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    aggregate = _aggregate(results)
    Path(args.output_json).write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    _write_md_report(Path(args.output_md), aggregate)

    print(f"\nSUMMARY pass_rate={aggregate['overall_pass_rate']} avg_runtime_ms={aggregate['overall_avg_runtime_ms']}")
    for row in aggregate["summary"]:
        print(
            f"  {row['scenario']:18} {row['style']:8} pass_rate={row['pass_rate']} "
            f"variance={row['variance']} reason={row['dominant_failure_reason']}"
        )
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
