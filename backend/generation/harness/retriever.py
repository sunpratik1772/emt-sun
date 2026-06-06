"""
Context retriever for the agent harness.

Given a classified Intent, gathers the right context for the LLM:
  - Node I/O contracts (filtered to relevant types when possible)
  - Dataset schemas (filtered to referenced data sources)
  - Template skeletons (best-match from TemplateRegistry)
  - Example workflows (loaded from templates/ as few-shot examples)
  - Memory (persisted copilot memory from prior sessions)

The retriever does NOT build the prompt — it collects raw materials.
PromptBuilder consumes the retrieved context to assemble the final
system/user prompts.

Design: no LLM calls, no network. Everything comes from local files
and registries. Fast enough to call on every request (~5ms).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .intent import Intent
from .memory import MemoryManager


@dataclass
class RetrievedContext:
    """Everything the prompt builder needs beyond the raw scenario."""

    intent: Intent
    matched_skills: list[str] = field(default_factory=list)
    template_name: str | None = None
    template_skeleton: dict | None = None
    template_parameters: list[dict] = field(default_factory=list)
    example_workflows: list[dict] = field(default_factory=list)
    memory_text: str = ""
    dataset_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "matched_skills": self.matched_skills,
            "template_name": self.template_name,
            "has_template": self.template_skeleton is not None,
            "example_count": len(self.example_workflows),
            "has_memory": bool(self.memory_text),
            "dataset_names": self.dataset_names,
        }


class ContextRetriever:
    """Gathers relevant context for a generation/edit request."""

    def __init__(
        self,
        memory: MemoryManager | None = None,
        templates_dir: Path | str | None = None,
    ) -> None:
        self.memory = memory or MemoryManager()
        self._templates_dir = Path(templates_dir) if templates_dir else (
            Path(__file__).resolve().parents[2] / "templates"
        )
        self._template_registry = None

    def _get_template_registry(self):
        if self._template_registry is None:
            from ..templates import TemplateRegistry
            self._template_registry = TemplateRegistry.from_directory(self._templates_dir)
        return self._template_registry

    def retrieve(self, intent: Intent) -> RetrievedContext:
        """Collect all context needed for generation/editing."""
        ctx = RetrievedContext(intent=intent)

        ctx.matched_skills = self._match_skills(intent)
        self._retrieve_template(intent, ctx)
        ctx.example_workflows = self._load_examples(intent, exclude=ctx.template_name)
        ctx.memory_text = self.memory.load()
        ctx.dataset_names = list(intent.datasets)

        return ctx

    def _match_skills(self, intent: Intent) -> list[str]:
        """Delegate to PromptBuilder's skill matcher."""
        try:
            from ..prompt_builder import PromptBuilder
            pb = PromptBuilder()
            return pb.match_skills(intent.raw_scenario)
        except Exception:
            return []

    def _retrieve_template(self, intent: Intent, ctx: RetrievedContext) -> None:
        """Find best-matching template skeleton for this intent."""
        if intent.mode == "edit":
            return

        registry = self._get_template_registry()
        match = registry.select({
            "scenarios": list(intent.scenarios),
            "datasets": list(intent.datasets),
        })
        if match is None:
            return

        ctx.template_name = match.template.name
        ctx.template_skeleton = match.template.skeleton
        ctx.template_parameters = [
            dict(p) for p in match.template.parameters
        ]

    def _load_examples(
        self,
        intent: Intent,
        exclude: str | None = None,
        max_examples: int = 2,
    ) -> list[dict]:
        """Load only vetted Studio demo workflows as few-shot context.

        Drafts and ad-hoc generated workflows can contain stale tool names.
        Keep examples constrained to backend/good_examples/studio_*.json — hand-tested
        Studio demos separate from user workloads in the DB.
        """
        examples: list[dict] = []
        from engine.demo_paths import demo_workflows_dir

        examples_dir = demo_workflows_dir()

        for path in sorted(examples_dir.glob("studio_*.json")):
            try:
                skeleton = json.loads(path.read_text())
            except Exception:
                continue

            relevance = 0
            name = skeleton.get("name") or path.stem
            description = skeleton.get("description") or ""
            if name == exclude:
                continue
            for s in intent.scenarios:
                haystack = f"{path.name} {name} {description}".lower()
                if s in haystack:
                    relevance += 5
            for d in intent.datasets:
                if d in json.dumps(skeleton):
                    relevance += 1

            if relevance > 0 or len(examples) < 1:
                examples.append({
                    "name": name,
                    "description": description,
                    "relevance": relevance,
                    "skeleton": skeleton,
                })

        examples.sort(key=lambda e: -e["relevance"])
        return examples[:max_examples]
