"""Live hello-world probe against the shared GeminiAdapter singleton."""
from __future__ import annotations

import pytest


def _gemini_configured() -> bool:
    try:
        from llm import gemini_configured

        return bool(gemini_configured())
    except Exception:
        return False


@pytest.mark.skipif(not _gemini_configured(), reason="GEMINI_API_KEY or Vertex project not configured")
def test_probe_gemini_connection_live() -> None:
    from llm import get_default_adapter, probe_gemini_connection

    a = get_default_adapter()
    b = get_default_adapter()
    assert a is b

    result = probe_gemini_connection()
    assert result.ok, result.message
    assert result.latency_ms is not None
    assert result.provider in ("gemini", "vertex")
