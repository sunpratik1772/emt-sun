#!/usr/bin/env python3
"""Run disposition matrix and print a UI-parity report."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from tests.intent_disposition_matrix_cases import INTENT_DISPOSITION_MATRIX
from tests.test_intent_disposition_matrix_live import _assert_case, _classify_case, _gemini_configured


def main() -> int:
    live = _gemini_configured()
    print(f"Gemini live: {live}")
    print(f"Cases: {len(INTENT_DISPOSITION_MATRIX)}\n")
    passed = 0
    failed = 0
    skipped = 0
    rows: list[str] = []

    for case in INTENT_DISPOSITION_MATRIX:
        if not live and case.case_id not in {
            "02_show_fix_plan_followup",
            "03_sample_run_yes",
            "04_canvas_edit_yes",
            "08_named_run_sample",
            "09_improve_existing_named",
            "13_do_it_after_run_review",
            "17_slash_style_build",
        }:
            skipped += 1
            rows.append(f"SKIP  {case.case_id:28} {case.description} (no Gemini)")
            continue
        try:
            resp = _classify_case(case)
            _assert_case(case, resp)
            disp = resp.disposition.kind if resp.disposition else resp.metadata.sherpa_disposition
            clar = "clarify" if resp.clarification and resp.clarification.needed else "—"
            plan = "plan" if resp.metadata.propose_build_plan else "—"
            fix = "fix" if resp.metadata.propose_fix_plan else "—"
            rows.append(
                f"PASS  {case.case_id:28} intent={resp.intent:14} disp={disp or '—':8} "
                f"clar={clar:8} plan={plan:4} fix={fix:4}  {case.description}"
            )
            passed += 1
        except AssertionError as exc:
            rows.append(f"FAIL  {case.case_id:28} {case.description}\n        {exc}")
            failed += 1
        except Exception as exc:
            rows.append(f"ERR   {case.case_id:28} {case.description}\n        {exc}")
            failed += 1

    for line in rows:
        print(line)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
