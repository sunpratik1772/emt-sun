#!/usr/bin/env python3
"""Live E2E: leads.csv → filter score>80 → github create-issue."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

PROMPT = (
    "Extract `company` and `score` from `leads.csv`, `filter` for `score` > 80, "
    "then use `github` to create an issue for each high-score lead."
)


def main() -> int:
    from llm import gemini_configured
    from copilot.workflow_generator import WorkflowCopilot

    if not gemini_configured():
        print("ERROR: GEMINI_API_KEY not configured in backend/.env")
        return 1

    print("Running harness E2E with prompt:\n ", PROMPT, "\n", sep="")

    copilot = WorkflowCopilot()
    events: list[dict] = []
    for frame in copilot.generate_with_critic_stream(PROMPT, iterations=3):
        events.append(frame)
        t = frame.get("type")
        if t == "thinking":
            status = frame.get("status", "")
            step = frame.get("step", "")
            print(f"  [{status}] {step}")
        elif t == "workflow_created":
            print(f"  workflow_created: {frame.get('nodeCount')} nodes")
        elif t == "error":
            print(f"  ERROR: {frame.get('message')}")
        elif t == "done":
            print(f"  done: success={frame.get('success')}")

    done = next((e for e in reversed(events) if e.get("type") == "done"), None)
    if not done or not done.get("success"):
        print("\nFAILED — generation did not succeed.")
        err = next((e for e in reversed(events) if e.get("type") == "error"), None)
        if err:
            print("Last error:", err.get("message"))
        return 1

    wf_events = [e for e in events if e.get("type") == "workflow_created"]
    if not wf_events:
        print("\nFAILED — no workflow_created event.")
        return 1

    wf = wf_events[-1].get("workflow") or {}
    types = [n.get("type") for n in wf.get("nodes", [])]
    print("\nNode types:", " → ".join(types))

    checks = {
        "csv_extract or db_query": any(t in types for t in ("csv_extract", "db_query")),
        "filter": "filter" in types,
        "github": "github" in types,
    }
    for name, ok in checks.items():
        print(f"  {'✓' if ok else '✗'} {name}")

    if not all(checks.values()):
        print("\nFAILED — workflow missing expected nodes.")
        return 1

    gh = next(n for n in wf["nodes"] if n["type"] == "github")
    print("\nGitHub node config:", json.dumps(gh.get("config", {}), indent=2))

    print("\nPASSED — harness generated a valid leads→github workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
