#!/usr/bin/env python3
"""Run extended regression matrix and print report."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
load_dotenv(_BACKEND / ".env")

from tests.regression_disposition_cases import REGRESSION_DISPOSITION_CASES
from tests.test_intent_disposition_matrix_live import _assert_case, _classify_case, _gemini_configured
from tests.test_regression_disposition import OFFLINE_REGRESSION

OFFLINE_ONLY = OFFLINE_REGRESSION


def main() -> int:
    live = _gemini_configured()
    print(f"Gemini live: {live}")
    print(f"Regression cases: {len(REGRESSION_DISPOSITION_CASES)}\n")
    passed = failed = skipped = 0
    rows: list[str] = []

    for case in REGRESSION_DISPOSITION_CASES:
        if not live and case.case_id not in OFFLINE_ONLY:
            skipped += 1
            tags = ",".join(sorted(case.tags))
            rows.append(f"SKIP  {case.case_id:30} [{tags}] (no Gemini)")
            continue
        try:
            resp = _classify_case(case)
            _assert_case(case, resp)
            disp = resp.disposition.kind if resp.disposition else resp.metadata.sherpa_disposition
            clar = "Y" if resp.clarification and resp.clarification.needed else "-"
            tags = ",".join(sorted(case.tags))
            rows.append(
                f"PASS  {case.case_id:30} intent={resp.intent:14} disp={str(disp):8} "
                f"clar={clar}  [{tags}]"
            )
            passed += 1
        except AssertionError as exc:
            tags = ",".join(sorted(case.tags))
            rows.append(f"FAIL  {case.case_id:30} [{tags}]\n        {exc}")
            failed += 1
        except Exception as exc:
            rows.append(f"ERR   {case.case_id:30}\n        {exc}")
            failed += 1

    for line in rows:
        print(line)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
