"""
Persistent chat memory — OpenClaw-style memory.md with compaction.

Lifecycle:
  1. Chat starts  → load() reads memory.md into a string for the system prompt.
  2. Each turn    → observe() buffers notable facts (user prefs, error patterns,
                    workflow patterns, learned fixes).
  3. Chat ends    → compact() merges buffered facts into memory.md, deduplicates,
                    and rewrites. On next chat, load() picks up the compacted state.

The memory file is a flat Markdown document with sections. Compaction uses
the LLM to merge old + new facts into a concise update (max ~2000 chars).
When no LLM is available, raw append + truncation keeps the file bounded.

Thread-safe: a file lock prevents concurrent writes from overlapping
sessions. Reads are lock-free (stale reads are acceptable for prompt
injection — the LLM handles minor staleness gracefully).
"""
from __future__ import annotations

import fcntl
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_DEFAULT_MEMORY_DIR = Path(__file__).resolve().parents[2] / "copilot" / "memory"
_MAX_MEMORY_CHARS = 2500
_MAX_BUFFER_ITEMS = 30

_EMPTY_MEMORY = """# Copilot Memory

## User Preferences

## Workflow Patterns

## Learned Fixes

## Recent Context

## Decisions

## Blockers

## Task Outputs

## Token Stats
"""

_SKIP_MEMORY_PATTERNS = re.compile(
    r"|".join(
        (
            r"\{\{[^}]+\}\}",
            r'"node_output"\s*:',
            r"'node_output'\s*:",
            r'"rows"\s*:\s*\[',
            r"Enriched\s+\d+/\d+\s+rows",
            r"^\s*\|[^|]+\|[^|]+\|",
            r"node_output\s*=\s*\{",
            r"columns?\s*:\s*\[",
        )
    ),
    re.IGNORECASE | re.MULTILINE,
)


def _should_skip_memory_fact(text: str) -> bool:
    """Drop debug dumps, template placeholders, and table noise from long-term memory."""
    stripped = (text or "").strip()
    if not stripped:
        return True
    if len(stripped) > 500 and stripped.startswith(("{", "[")):
        return True
    if _SKIP_MEMORY_PATTERNS.search(stripped):
        return True
    if stripped.count("|") >= 6 and stripped.count("\n") >= 2:
        return True
    return False


@dataclass
class MemoryManager:
    """Read/write/compact copilot memory — per-user DB row or legacy memory.md."""

    memory_dir: Path = field(default_factory=lambda: _DEFAULT_MEMORY_DIR)
    user_id: str | None = None
    _buffer: list[str] = field(default_factory=list, repr=False)
    runtime_recent_turns: list[str] = field(default_factory=list, repr=False)
    runtime_decisions: list[str] = field(default_factory=list, repr=False)
    runtime_blockers: list[str] = field(default_factory=list, repr=False)
    runtime_task_outputs: list[str] = field(default_factory=list, repr=False)
    runtime_token_stats: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.memory_dir = Path(self.memory_dir)

    @property
    def memory_path(self) -> Path:
        return self.memory_dir / "memory.md"

    def bind_user(self, user_id: str | None) -> None:
        """Attach a user for per-user DB persistence (set per copilot request)."""
        self.user_id = user_id

    def _resolved_user_id(self) -> str | None:
        return self.user_id

    # ── Read ────────────────────────────────────────────────────────────
    def load(self) -> str:
        """Return the current memory content for injection into the system prompt."""
        uid = self._resolved_user_id()
        if uid:
            try:
                from app.database_scope import get_user_memory_content

                text = get_user_memory_content(uid).strip()
                if text:
                    return text
            except Exception:
                pass
        if not self.memory_path.exists():
            return ""
        try:
            text = self.memory_path.read_text(encoding="utf-8").strip()
            return text if text else ""
        except Exception:
            return ""

    # ── Buffer ──────────────────────────────────────────────────────────
    def observe(self, fact: str, *, category: str = "Recent Context") -> None:
        """Buffer a notable fact from the current turn.

        Categories: User Preferences, Workflow Patterns, Learned Fixes,
        Recent Context. The category determines which section the fact
        lands in during compaction.
        """
        if not fact or not fact.strip() or _should_skip_memory_fact(fact):
            return
        entry = f"[{category}] {fact.strip()}"
        self._buffer.append(entry)
        if len(self._buffer) > _MAX_BUFFER_ITEMS:
            self._buffer = self._buffer[-_MAX_BUFFER_ITEMS:]

    def observe_turn(self, text: str) -> None:
        if not text or not text.strip() or _should_skip_memory_fact(text):
            return
        self.runtime_recent_turns.append(text.strip()[:240])
        self.runtime_recent_turns = self.runtime_recent_turns[-20:]
        self.observe(text, category="Recent Context")

    def note_decision(self, text: str) -> None:
        if not text or not text.strip():
            return
        self.runtime_decisions.append(text.strip())
        self.runtime_decisions = self.runtime_decisions[-20:]
        self.observe(text, category="Decisions")

    def note_blocker(self, text: str) -> None:
        if not text or not text.strip():
            return
        self.runtime_blockers.append(text.strip())
        self.runtime_blockers = self.runtime_blockers[-20:]
        self.observe(text, category="Blockers")

    def note_task_output(self, text: str) -> None:
        if not text or not text.strip() or _should_skip_memory_fact(text):
            return
        self.runtime_task_outputs.append(text.strip()[:300])
        self.runtime_task_outputs = self.runtime_task_outputs[-30:]
        self.observe(text, category="Task Outputs")

    def note_token_stats(self, used: int, budget: int) -> None:
        entry = f"used={used} budget={budget}"
        if self.runtime_token_stats and self.runtime_token_stats[-1] == entry:
            return
        self.runtime_token_stats.append(entry)
        self.runtime_token_stats = self.runtime_token_stats[-40:]
        self.observe(entry, category="Token Stats")

    def observe_workflow_result(
        self,
        workflow_name: str,
        node_count: int,
        success: bool,
        errors: list[dict] | None = None,
    ) -> None:
        """Record a workflow generation/edit outcome."""
        status = "succeeded" if success else "failed"
        self.observe(
            f"Workflow '{workflow_name}' ({node_count} nodes) {status}",
            category="Recent Context",
        )
        if errors:
            codes = [e.get("code", "?") for e in errors[:3]]
            self.observe(
                f"Common errors: {', '.join(codes)}",
                category="Learned Fixes",
            )

    def observe_user_preference(self, pref: str) -> None:
        """Record a user preference (e.g. 'prefers Excel over CSV')."""
        self.observe(pref, category="User Preferences")

    def observe_edit_pattern(self, description: str) -> None:
        """Record a workflow editing pattern."""
        self.observe(description, category="Workflow Patterns")

    # ── Compact ─────────────────────────────────────────────────────────
    def compact(self, llm_compact_fn: Any = None) -> str:
        """Merge buffered facts into memory.md and rewrite.

        If `llm_compact_fn` is provided, it's called as:
            llm_compact_fn(old_memory: str, new_facts: list[str]) -> str
        to produce a concise merged memory. Otherwise falls back to
        deterministic append + truncation.

        Returns the new memory content.
        """
        if not self._buffer:
            return self.load()

        old = self.load()
        new_facts = list(self._buffer)
        self._buffer.clear()

        if llm_compact_fn:
            try:
                compacted = llm_compact_fn(old, new_facts)
                if isinstance(compacted, str) and compacted.strip():
                    self._write(compacted.strip())
                    return compacted.strip()
            except Exception:
                pass

        merged = self._deterministic_compact(old, new_facts)
        self._write(merged)
        return merged

    def _deterministic_compact(self, old: str, new_facts: list[str]) -> str:
        """Append new facts to appropriate sections, truncate if needed."""
        sections: dict[str, list[str]] = {
            "User Preferences": [],
            "Workflow Patterns": [],
            "Learned Fixes": [],
            "Recent Context": [],
            "Decisions": [],
            "Blockers": [],
            "Task Outputs": [],
            "Token Stats": [],
        }

        for line in old.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                for section in sections:
                    if f"## {section}" in old[:old.index(stripped)]:
                        sections[section].append(stripped)
                        break

        for fact in new_facts:
            category = "Recent Context"
            for section in sections:
                if fact.startswith(f"[{section}]"):
                    category = section
                    fact = fact[len(f"[{section}]"):].strip()
                    break
            entry = f"- {fact}"
            if entry not in sections[category]:
                sections[category].append(entry)

        # Keep sections bounded
        for key in sections:
            max_items = 5 if key == "Recent Context" else 8
            if key in {"Decisions", "Task Outputs", "Token Stats"}:
                max_items = 10
            if key == "Blockers":
                max_items = 6
            sections[key] = sections[key][-max_items:]

        lines = ["# Copilot Memory", ""]
        for section, items in sections.items():
            lines.append(f"## {section}")
            lines.extend(items)
            lines.append("")

        result = "\n".join(lines).strip()
        if len(result) > _MAX_MEMORY_CHARS:
            result = result[:_MAX_MEMORY_CHARS].rsplit("\n", 1)[0]
        return result

    def _write(self, content: str) -> None:
        """Persist memory to per-user DB or legacy memory.md."""
        uid = self._resolved_user_id()
        if uid:
            try:
                from app.database_scope import save_user_memory_content

                save_user_memory_content(uid, content)
                return
            except Exception:
                pass
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.memory_dir / ".memory.lock"
        try:
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    self.memory_path.write_text(content, encoding="utf-8")
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except Exception:
            self.memory_path.write_text(content, encoding="utf-8")

    def clear(self) -> None:
        """Reset memory to empty state."""
        self._buffer.clear()
        self._write(_EMPTY_MEMORY.strip())
