#!/usr/bin/env python3
"""Dev-only: run demo_showcase workflows from CLI. Studio users should use Run in the UI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_SHOWCASE = _BACKEND / "workflows" / "demo_showcase"


def main() -> None:
    sys.path.insert(0, str(_BACKEND))
    from dotenv import load_dotenv

    load_dotenv(_BACKEND / ".env")
    import os
    from llm import gemini_configured

    if not gemini_configured():
        raise SystemExit(
            "GEMINI_API_KEY required in backend/.env — Studio demos use real Gemini only."
        )

    from scripts.run_demo_workflow import _ensure_bridge, _needs_mcp
    from engine.copilot_validate import validate_dag_for_api
    from engine.dag_runner import run_workflow

    paths = sorted(_SHOWCASE.glob("demo_*.json"))
    if not paths:
        raise SystemExit(f"No demos in {_SHOWCASE}")

    bridge = None
    ok, fail = [], []

    for path in paths:
        dag = json.loads(path.read_text())
        if _needs_mcp(dag) and bridge is None:
            bridge = _ensure_bridge()
        vr = validate_dag_for_api(dag)
        if not vr.valid:
            fail.append((path.name, f"validation: {vr.errors}"))
            continue
        try:
            ctx = run_workflow(dag, {})
            last = dag["nodes"][-1]["id"]
            out = ctx.output_map.get(last, {})
            hint = out.get("rowCount") or out.get("rowsWritten") or len(out.get("rows") or [])
            ok.append((path.name, str(hint)))
        except Exception as exc:
            fail.append((path.name, str(exc)))

    if bridge:
        bridge.terminate()

    print("\n=== Passed ===")
    for name, hint in ok:
        print(f"  ✓ {name} ({hint})")
    if fail:
        print("\n=== Failed ===")
        for name, err in fail:
            print(f"  ✗ {name}: {err[:200]}")
        raise SystemExit(1)
    print(f"\n{len(ok)}/{len(paths)} showcase demos OK")
    print("Studio: open workflows/demo_join_analyze_confluence.json and click Run.")


if __name__ == "__main__":
    main()
