from __future__ import annotations

import random
from typing import Mapping


def compute_retry_delay_ms(
    attempt: int,
    *,
    headers: Mapping[str, str] | None = None,
    base_ms: int = 400,
    cap_ms: int = 20000,
) -> int:
    headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return min(cap_ms, max(0, int(float(retry_after) * 1000)))
        except Exception:
            pass

    expo = base_ms * (2 ** max(0, attempt - 1))
    jitter = random.randint(0, base_ms)
    return min(cap_ms, expo + jitter)
