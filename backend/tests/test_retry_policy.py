from __future__ import annotations

from generation.harness.retry_policy import compute_retry_delay_ms


def test_retry_policy_uses_retry_after_header() -> None:
    delay = compute_retry_delay_ms(1, headers={"Retry-After": "2"})
    assert delay == 2000


def test_retry_policy_backoff_increases_with_attempt() -> None:
    d1 = compute_retry_delay_ms(1, headers={})
    d2 = compute_retry_delay_ms(2, headers={})
    assert d2 >= d1
