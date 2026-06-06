"""Search saved workflows in the DB with scored top-N matching."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


_STOPWORDS = frozenset({
    "a", "an", "the", "my", "this", "that", "load", "open", "get", "show",
    "workflow", "workflows", "pipeline", "pipelines", "run", "please",
})


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 2 and t not in _STOPWORDS]


def _score_field(query_tokens: list[str], field: str | None, *, weight: float) -> tuple[float, list[str]]:
    if not field:
        return 0.0, []
    lower = field.lower()
    reasons: list[str] = []
    score = 0.0
    joined = " ".join(query_tokens)

    if joined and joined in lower:
        score += weight * 1.0
        reasons.append(f"phrase match in '{field[:48]}'")

    for tok in query_tokens:
        if tok in lower:
            score += weight * 0.35
            if f"token '{tok}'" not in " ".join(reasons):
                reasons.append(f"token '{tok}'")

    return score, reasons


def score_workflow_row(query: str, row: dict[str, Any]) -> tuple[float, list[str]]:
    """Score a workflows-table row against a natural-language query."""
    q = (query or "").strip()
    if not q:
        return 0.0, []

    query_tokens = _tokens(q)
    if not query_tokens:
        return 0.0, []

    dag: dict[str, Any] = {}
    raw = row.get("workflow_data")
    if raw:
        try:
            dag = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            dag = {}

    filename = str(row.get("filename") or "")
    name = str(row.get("name") or dag.get("name") or "")
    workflow_id = str(row.get("workflow_id") or dag.get("workflow_id") or "")
    description = str(row.get("description") or dag.get("description") or "")

    total = 0.0
    reasons: list[str] = []

    for field, weight in (
        (name, 3.0),
        (workflow_id, 2.5),
        (filename, 2.0),
        (description, 1.5),
    ):
        part, part_reasons = _score_field(query_tokens, field, weight=weight)
        total += part
        reasons.extend(part_reasons[:2])

    # Exact filename (without path) wins outright.
    if filename.lower() == q.lower() or filename.lower() == f"{q.lower()}.json":
        total += 10.0
        reasons.insert(0, "exact filename")

    return total, reasons[:4]


@dataclass(frozen=True)
class WorkflowMatch:
    filename: str
    name: str
    workflow_id: str | None
    description: str | None
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "name": self.name,
            "workflow_id": self.workflow_id,
            "description": self.description,
            "score": round(self.score, 3),
            "reasons": self.reasons,
        }


def search_workflows(
    rows: list[dict[str, Any]],
    query: str,
    *,
    limit: int = 3,
    min_score: float = 0.35,
) -> dict[str, Any]:
    """Return load / disambiguate / not_found for a query against workflow rows."""
    limit = max(1, min(int(limit), 3))
    scored: list[WorkflowMatch] = []

    for row in rows:
        score, reasons = score_workflow_row(query, row)
        if score < min_score:
            continue
        dag = {}
        raw = row.get("workflow_data")
        if raw:
            try:
                dag = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                pass
        scored.append(
            WorkflowMatch(
                filename=str(row.get("filename") or ""),
                name=str(row.get("name") or dag.get("name") or row.get("filename") or ""),
                workflow_id=row.get("workflow_id") or dag.get("workflow_id"),
                description=row.get("description") or dag.get("description"),
                score=score,
                reasons=reasons,
            )
        )

    scored.sort(key=lambda m: (-m.score, m.name.lower()))

    if not scored:
        return {"action": "not_found", "query": query, "matches": []}

    top = scored[:limit]

    # Clear winner: much higher score than #2, or exact filename match.
    if len(top) == 1:
        winner = top[0]
        dag = _load_dag(rows, winner.filename)
        return {
            "action": "load",
            "query": query,
            "match": winner.to_dict(),
            "workflow": dag,
        }

    if top[0].score >= top[1].score * 1.75 or "exact filename" in top[0].reasons:
        winner = top[0]
        dag = _load_dag(rows, winner.filename)
        return {
            "action": "load",
            "query": query,
            "match": winner.to_dict(),
            "workflow": dag,
        }

    return {
        "action": "disambiguate",
        "query": query,
        "matches": [m.to_dict() for m in top],
        "message": (
            f"I found {len(top)} likely matches — did you mean one of these?"
            if len(top) > 1
            else "I found a possible match."
        ),
    }


def _load_dag(rows: list[dict[str, Any]], filename: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("filename") != filename:
            continue
        raw = row.get("workflow_data")
        if not raw:
            return None
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return None
    return None
