from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompactionInput:
    goal: str
    constraints: list[str] = field(default_factory=list)
    done: list[str] = field(default_factory=list)
    in_progress: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    critical_context: list[str] = field(default_factory=list)
    relevant_files: list[str] = field(default_factory=list)


def render_compacted_summary(data: CompactionInput) -> str:
    def _bullets(items: list[str], fallback: str = "- (none)") -> str:
        if not items:
            return fallback
        return "\n".join(f"- {item}" for item in items)

    return (
        "## Goal\n"
        f"{data.goal.strip() or '(unspecified goal)'}\n\n"
        "## Constraints & Preferences\n"
        f"{_bullets(data.constraints)}\n\n"
        "## Progress\n"
        "### Done\n"
        f"{_bullets(data.done)}\n"
        "### In Progress\n"
        f"{_bullets(data.in_progress)}\n"
        "### Blocked\n"
        f"{_bullets(data.blocked)}\n\n"
        "## Key Decisions\n"
        f"{_bullets(data.decisions)}\n\n"
        "## Next Steps\n"
        f"{_bullets(data.next_steps)}\n\n"
        "## Critical Context\n"
        f"{_bullets(data.critical_context)}\n\n"
        "## Relevant Files\n"
        f"{_bullets(data.relevant_files)}\n"
    )


def compact_history(
    history: list[dict],
    *,
    preserve_tail_messages: int = 4,
) -> tuple[str, list[dict]]:
    if len(history) <= preserve_tail_messages:
        return "", history

    older = history[:-preserve_tail_messages]
    recent = history[-preserve_tail_messages:]
    snippets = []
    for msg in older:
        role = msg.get("role", "unknown")
        content = str(msg.get("content", "")).strip().replace("\n", " ")
        snippets.append(f"{role}: {content[:220]}")

    summary = render_compacted_summary(
        CompactionInput(
            goal="Continue the same workflow generation request with compacted context.",
            constraints=["Preserve correctness and existing user intent."],
            done=["Historical messages compacted for token budget."],
            in_progress=["Validation and repair loop may continue."],
            blocked=[],
            decisions=["Recent message tail is preserved verbatim."],
            next_steps=["Use the compact summary plus recent messages to continue."],
            critical_context=snippets[-12:],
            relevant_files=[],
        )
    )
    return summary, recent
