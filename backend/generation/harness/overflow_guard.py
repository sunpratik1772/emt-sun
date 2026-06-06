from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OverflowDecision:
    max_input_tokens: int
    reserved_tokens: int
    usable_tokens: int
    estimated_tokens: int
    overflow: bool


_MODEL_LIMITS = {
    "default": 32000,
    "gemini": 32000,
    "claude": 200000,
    "gpt": 128000,
}


def _estimate_tokens(text: str) -> int:
    # Fast approximation good enough for guardrail checks.
    return max(1, len(text) // 4)


def compute_overflow(
    text: str,
    *,
    model_hint: str = "default",
    reserved_tokens: int | None = None,
) -> OverflowDecision:
    model_key = (model_hint or "default").lower()
    max_input = _MODEL_LIMITS.get(model_key, _MODEL_LIMITS["default"])
    reserve = reserved_tokens
    if reserve is None:
        reserve = int(os.environ.get("HARNESS_OVERFLOW_RESERVED_TOKENS", "3000") or "3000")
    usable = max(512, max_input - max(0, reserve))
    estimated = _estimate_tokens(text or "")
    return OverflowDecision(
        max_input_tokens=max_input,
        reserved_tokens=reserve,
        usable_tokens=usable,
        estimated_tokens=estimated,
        overflow=estimated > usable,
    )
