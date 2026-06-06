"""Call Gemini with optional row context via the shared ``GeminiAdapter``."""
from __future__ import annotations

import json as _json
import logging
from pathlib import Path
from typing import Any

from llm import gemini_configured, get_default_adapter
from runtime_env import ensure_env_loaded

from ..context import RunContext
from ..node_spec import _spec_from_yaml
from ..row_template import interpolate_row_template

_HERE = Path(__file__).parent
ensure_env_loaded()

logger = logging.getLogger(__name__)


def _upstream_rows(incoming: dict[str, Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            merged.extend(out["rows"])
    return merged


def _per_row_user_msg(
    prompt: str,
    task: str,
    row_template: str,
    row: dict[str, Any],
) -> str:
    parts: list[str] = []
    if prompt.strip():
        parts.append(interpolate_row_template(prompt, row))
    if task.strip():
        parts.append(interpolate_row_template(task, row))
    if row_template.strip():
        parts.append(interpolate_row_template(row_template, row))
    return "\n\n".join(parts).strip()


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    rows = _upstream_rows(incoming)
    model_name = cfg.get("model") or "gemini-2.5-flash"
    prompt = cfg.get("prompt") or ""
    task = cfg.get("task") or "Provide a concise summary."

    if not gemini_configured():
        raise ValueError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set in backend/.env. "
            "Restart the backend after adding your key."
        )

    adapter = get_default_adapter()

    if cfg.get("perRow") and rows:
        out_col = cfg.get("outputColumn") or "_ai_response"
        cap = int(cfg.get("maxRows") or 5)
        configured_template = str(cfg.get("rowTemplate") or "").strip()
        enriched: list[dict[str, Any]] = []
        for i, r in enumerate(rows):
            if i >= cap:
                enriched.append(r)
                continue
            row_template = configured_template or _json.dumps(r, default=str)
            user_msg = _per_row_user_msg(prompt, task, row_template, r)
            try:
                text = adapter.single_shot(user_msg, model=model_name).strip()
            except Exception as exc:
                logger.exception("Agent per-row call failed")
                raise RuntimeError(f"Gemini per-row call failed: {exc}") from exc
            enriched.append({**r, out_col: text})
        return {
            "model": model_name,
            "response": f"Enriched {min(cap, len(rows))}/{len(rows)} rows",
            "rows": enriched,
            "rowCount": len(enriched),
            "tokensIn": 0,
            "tokensOut": 0,
        }

    user_msg = (
        f"{prompt}\n\n{task}\n\nData:\n{_json.dumps(rows[:50], indent=2, default=str)}"
        if rows
        else f"{prompt}\n\n{task}"
    )
    try:
        text = adapter.single_shot(user_msg, model=model_name).strip()
        out_rows: list[dict[str, Any]] = list(rows)
        if cfg.get("emitPublishRow"):
            page_title = cfg.get("pageTitle") or "Studio workflow analysis"
            out_rows = [
                {
                    "title": page_title,
                    "body_markdown": text,
                    "metrics_preview": rows[:25],
                    "source_row_count": len(rows),
                }
            ]
        if not out_rows and text:
            out_rows = [{"response": text, "briefing": text}]
        elif out_rows and text and not cfg.get("emitPublishRow"):
            out_rows = [{**r, "ai_summary": text} if isinstance(r, dict) else r for r in out_rows]
        return {
            "model": model_name,
            "response": text,
            "tokensIn": 0,
            "tokensOut": 0,
            "rows": out_rows,
            "rowCount": len(out_rows),
        }
    except Exception as exc:
        logger.exception("Agent call failed")
        raise RuntimeError(f"Gemini call failed: {exc}") from exc


NODE_SPEC = _spec_from_yaml(_HERE / "agent.yaml", run)
