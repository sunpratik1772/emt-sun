"""
/agent/* endpoints.

Currently only exposes a read-only metrics snapshot used by the UI
status strip + CI regression checks. Future additions live here:
  - GET /agent/attempts/:id  (per-run trace)
  - POST /agent/autofix      (run auto-fixer standalone for a DAG)
"""
from __future__ import annotations

from fastapi import APIRouter

from generation.harness.metrics import get_metrics
from llm import gemini_configured, llm_provider, probe_gemini_connection

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/metrics")
def metrics() -> dict:
    """Return a snapshot of in-process agent metrics.

    These reset on process restart. Think of them as a dev/ops
    dashboard feed rather than long-term telemetry.
    """
    return get_metrics().snapshot()


@router.post("/metrics/reset")
def reset_metrics() -> dict:
    """Zero all counters. Handy during a demo or after a regression fix."""
    get_metrics().reset()
    return {"status": "ok"}


@router.get("/llm/health")
def llm_health() -> dict:
    """LLM credential presence (no network call)."""
    return {
        "configured": gemini_configured(),
        "provider": llm_provider(),
    }


@router.get("/llm/probe")
def llm_probe() -> dict:
    """Hello-world Gemini/Vertex connectivity via the shared ``GeminiAdapter``."""
    result = probe_gemini_connection()
    return {
        "ok": result.ok,
        "provider": result.provider,
        "model": result.model,
        "message": result.message,
        "latency_ms": result.latency_ms,
    }
