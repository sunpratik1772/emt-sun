"""
Prompt construction for the agent.

Three surfaces:
  - `system_prompt(skills, contracts)` — the stable instruction block
    the LLM receives once. Unchanged from the old WorkflowCopilot, but
    lives here so we can unit-test and iterate on it independently.
  - `initial_prompt(scenario, …)` — the first user turn. When the
    caller passes `current_workflow` (and optionally `recent_errors`)
    we switch to edit-mode: the prompt shows the existing DAG, lists
    any failures, and asks for a targeted edit that preserves node
    IDs and labels where possible.
  - `repair_prompt(errors, attempt, total)` — subsequent user turns,
    delegated to FeedbackBuilder for the hard formatting work.

Keeping these pure functions (no LLM, no network) makes prompt
regression-tests straightforward.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from connectors import get_registry
from engine.node_availability import is_agent_visible_type
from engine.mcp_nodes import active_mcp_node_types
from .harness.instruction_resolver import InstructionResolver
from .repair.feedback_builder import build_feedback


ALWAYS_ON_SKILLS = ("skills-agentic-workflow-builder",)


class PromptBuilder:
    def __init__(
        self,
        skills_dir: Path | str = "skills",
        contracts_path: Path | str = "contracts/node_contracts.json",
    ) -> None:
        self.skills_dir = _resolve_backend_path(skills_dir)
        self.contracts_path = Path(contracts_path)
        self.instruction_resolver = InstructionResolver(
            project_root=Path(__file__).resolve().parents[1]
        )

    # ── system ----------------------------------------------------------------
    def _load_skills(self) -> str:
        if not self.skills_dir.exists():
            return "(no skill files found)"
        chunks = [
            f"=== {p.stem} ===\n{p.read_text()}"
            for p in sorted(self.skills_dir.glob("*.md"))
        ]
        return "\n\n".join(chunks) if chunks else "(no skill files found)"

    def _load_contracts(self) -> str:
        # The LLM must see the same NodeSpec contracts that `/contracts` and
        # `/node-manifest` expose. Falling back to the checked-in artifact is
        # only for unusual import/bootstrap failures; it is no longer the
        # normal source of truth.
        try:
            from engine.registry import contracts_document

            return json.dumps(contracts_document(studio_only=True), indent=2)
        except Exception:
            if self.contracts_path.exists():
                return self.contracts_path.read_text()
        return "{}"

    def _load_generation_guardrails(self) -> str:
        path = Path(__file__).resolve().parent / "generation_guardrails.md"
        if not path.exists():
            return "(no generation guardrails file found)"
        text = path.read_text(encoding="utf-8").strip()
        return text or "(generation guardrails file is empty)"

    def _known_node_types(self) -> set[str]:
        try:
            from engine.registry import NODE_SPECS
            return {str(t).upper() for t in NODE_SPECS.keys()}
        except Exception:
            return set()

    def _infer_target_nodes(
        self,
        scenario: str | None = None,
        current_workflow: dict[str, Any] | None = None,
    ) -> list[str]:
        known = self._known_node_types()
        selected: set[str] = set()
        if current_workflow:
            for node in current_workflow.get("nodes", []) or []:
                t = str((node or {}).get("type", "")).upper().strip()
                if t:
                    selected.add(t)
        if scenario:
            for token in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", scenario):
                t = token.strip().upper()
                if t in known:
                    selected.add(t)
        return sorted(selected)

    def _filter_guardrails_for_nodes(self, full_text: str, nodes: list[str]) -> str:
        if not full_text.strip() or not nodes:
            return full_text
        want = {n.upper() for n in nodes}
        lines = full_text.splitlines()
        if not lines:
            return full_text

        first_node_rule_idx = next(
            (i for i, ln in enumerate(lines) if re.match(r"^\s*-\s*`", ln)),
            len(lines),
        )
        global_prefix = "\n".join(lines[:first_node_rule_idx]).strip()

        blocks: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            is_node_rule = bool(re.match(r"^\s*-\s*`", line)) or bool(re.match(r"^\s*\d+\)\s+`", line))
            if not is_node_rule:
                i += 1
                continue
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if re.match(r"^\s*-\s*`", nxt) or re.match(r"^\s*\d+\)\s+`", nxt):
                    break
                j += 1
            block = "\n".join(lines[i:j]).strip()
            names = {m.upper() for m in re.findall(r"`([A-Za-z0-9_]+)`", lines[i])}
            if names & want:
                blocks.append(block)
            i = j

        if not blocks:
            return full_text
        selected = [x for x in (global_prefix, *blocks) if x.strip()]
        return "\n\n".join(selected)

    def list_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return [p.stem for p in sorted(self.skills_dir.glob("*.md"))]

    def match_skills(self, scenario: str) -> list[str]:
        """Cheap heuristic skill matcher.

        A proper retriever would use embeddings; a trigram match on the
        file stems is 90% as good for the ~10 skills we ship and needs
        no ML dependency. We fall back to all skills when nothing
        tokenises — the system prompt always includes the full
        library, so "matched" is a display hint rather than a filter.
        """
        lower = scenario.lower()
        available = self.list_skills()
        matched = [
            s for s in self.list_skills()
            if any(tok and tok in lower for tok in s.lower().split("-"))
        ]
        out = matched or available
        for skill in ALWAYS_ON_SKILLS:
            if skill in available and skill not in out:
                out.insert(0, skill)
        return out

    def system_prompt(
        self,
        scenario: str | None = None,
        current_workflow: dict[str, Any] | None = None,
    ) -> str:
        self.instruction_resolver.begin_cycle()
        skills = self._load_skills()
        contracts = self._load_contracts()
        guardrails = self._load_generation_guardrails()
        targets = self._infer_target_nodes(scenario=scenario, current_workflow=current_workflow)
        guardrails = self._filter_guardrails_for_nodes(guardrails, targets)
        schema_hints = get_registry().schema_hints_for_prompt()
        provider = (os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()
        upload_scripts_enabled = os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() in {"1", "true", "yes"}
        upload_rule = (
            "upload_script is ENABLED on this host; use it only when a skill explicitly needs custom Python."
            if upload_scripts_enabled
            else "upload_script is DISABLED on this host."
        )
        mcp_node_list = ", ".join(f"`{t}`" for t in active_mcp_node_types()) or (
            "`jira_mcp`, `confluence_mcp`, `github_mcp`"
        )
        base_system = f"""You are dbSherpa Copilot — an AI workflow designer for Sheep Studio.

You generate complete, valid, executable DAG JSON workflows for the orchestrator engine.

## Mission
Given a user objective, output one workflow JSON that runs end-to-end and
produces requested artifacts (CSV, Excel, MCP publishes, GitHub issues, etc.)
when those are requested.

## Source of truth
- Node behavior and valid config keys come only from Node I/O Contracts.
- Dataset names/columns come only from Data Source Column Schemas.
- Domain guidance comes from the skills library.
- Host capability: {upload_rule}

## Core generation policy
1. Return ONLY one complete JSON object (no prose, no markdown fences).
2. Never invent node types, params, fields, refs, dataset names, or columns.
3. Every node must include: `id`, `type`, `label`, `config`.
4. Every edge must use: `{{"from":"<id>","to":"<id>"}}`.
5. Build an acyclic graph. Keep wiring explicit and execution-safe.
6. Use stable ids (`n01`, `n02`, ...) and preserve ids in edit mode unless required.
7. Prefer minimum viable topology that satisfies objective; avoid decorative nodes.
8. If objective is partially unsupported, implement the supported subset only.

## Studio runtime preferences
- Start with `manual_trigger` unless another trigger is explicitly requested.
- Load fixtures with `csv_extract` (`source`) or `db_query` for SQL datasets.
- For "sample companies from a public API", prefer `https://jsonplaceholder.typicode.com/users`.
- Shape rows with `filter`, `map_transform`, `group_by`, `sort`, `join`, `data_merge`.
- Branch with `condition` or `router`; use `code` only when declarative nodes cannot express the transform.
- Summarize or draft with `agent` when LLM output is requested.
- Integrate via {mcp_node_list} using contract-backed config.
- Never emit legacy `github` REST nodes or combined `mcp` nodes.
- For GitHub repo activity, use `github_mcp` with `tool: github_list_commits`, then `agent` + `confluence_mcp`.
- Use `github_implement_fixes` / `github_fix_jira_and_update` only for Jira-linked PR flows.
- For MCP nodes ({mcp_node_list}): set only `tool`, `pageTitle` (Confluence), and `params` in config. Never emit
  credential fields (`jiraSiteUrl`, `confluenceSpaceKey`, `*ApiToken`, `githubToken`, `githubRepo`, etc.) —
  those are loaded from backend/.env at runtime and are locked in the Studio inspector.
- End file asks with `csv_output` or `excel_output` using concrete paths.
- Do NOT emit retired n8n/dbSherpa node types (`SET`, `MERGE`, `LLM_BASIC`, `ALERT_TRIGGER`, …).
- If `code` is required, emit Starlark-only code (never Python): no `import`, no `from ... import`, no `try/except`, no class definitions.
- Starlark code must be formatted with professional indentation (4 spaces per block level) and must contain clear inline `#` comments at EVERY single logical step explaining what the code is doing. Never write compact, uncommented, or unindented code blocks.
- Every `code` node must include:
  - `code_summary` (plain-English explanation), and
  - inline `#` comments that guide reviewers through transformation steps.
- Starlark code must assign final rows to `output` (or `result` for compatibility).

## Generation guardrails (learned failure patterns)
Node-targeted guardrails selected for this request: {targets or ["(none inferred; using global guardrails)"]}
{guardrails}

## Node I/O Contracts
{contracts}

## Data Source Column Schemas
{schema_hints}

## Skills Library
{skills}

## Repair contract
When you receive REPAIR feedback, fix only listed issues and re-emit the full
workflow JSON. Keep unaffected sections stable.
"""
        provider_overlay = self._provider_overlay(provider)
        role_overlay = self._role_overlay()
        guardrail_slice = self._guardrail_slice(targets, guardrails)
        instruction_slice = self._instruction_slice()
        skill_slice = self._skill_slice(skills)
        return "\n\n".join(
            part
            for part in (
                base_system,
                provider_overlay,
                role_overlay,
                guardrail_slice,
                instruction_slice,
                skill_slice,
            )
            if part.strip()
        )

    def chat_system_prompt(self) -> str:
        """Q&A / advisory mode — explain platform capabilities, never emit workflow JSON."""
        schema_hints = get_registry().schema_hints_for_prompt()
        try:
            from engine.registry import studio_manifest

            manifest = studio_manifest()
            node_lines = [
                f"- {n['type_id']}: {n.get('description', '')[:120]}"
                for n in manifest.get("nodes", [])[:48]
            ]
            nodes_block = "\n".join(node_lines) if node_lines else "(node manifest unavailable)"
        except Exception:
            nodes_block = "(node manifest unavailable)"

        skills = self._load_skills()
        upload_scripts_enabled = os.environ.get("DBSHERPA_ALLOW_UPLOAD_SCRIPT", "").lower() in {
            "1",
            "true",
            "yes",
        }
        upload_rule = (
            "Custom Python upload_script nodes are enabled on this host."
            if upload_scripts_enabled
            else "Custom Python upload_script nodes are disabled; use built-in configure-mode nodes."
        )

        from copilot.next_action import NEXT_ACTION_PROMPT

        base = f"""You are sherpa — the AI assistant for dbSherpa Studio (Sheep workflow builder).

## Your role in Ask mode
Answer questions, explain failures, and outline recovery options.
Do NOT output workflow JSON. Do NOT pretend you rebuilt the canvas.

Help the user with:
- What went wrong (validator errors, runtime smoke failures, missing credentials)
- Concrete options to fix integrations (MCP, GitHub, etc.)
- Which nodes, data sources, and skills are available
- What information you still need before building or editing a workflow
- Step-by-step recovery paths ranked by effort (fastest fix first)

When the user asks "what are my options" or "how do I get this to work":
1. Name the primary blocker clearly.
2. List 2–4 actionable options (env vars, node config, alternate approach).
3. Say what you would need from them to proceed with a build or targeted fix.

If they want a new workflow or canvas edit, tell them to describe the change explicitly
(e.g. "build a workflow that…" or "fix the jira_mcp params") in Build mode.

## Row binding contract (critical for agent + MCP debugging)
Studio uses different placeholder dialects — do not mix them up:
- **filter / condition / map_transform**: JavaScript expressions with `row.field` (no braces).
- **agent per-row** (`perRow: true`): `rowTemplate` with `{{company}}` or `{{row.company}}`; also set `outputColumn`, `maxRows`.
- **MCP params** (Jira, etc.): JSON params with `{{row.poem}}` / `{{company}}` — rendered into each upstream row before the bridge call.
- **Jira bridge fields**: `summary`, `description` (aliases: `poem`→`description`, `company`→`summary`, `title`→`summary`).

If debug output still shows literal `{{row.company}}` in a poem column, the agent template was not interpolated — check `perRow` and `rowTemplate`, not the LLM prompt alone.
If MCP Jira issues have wrong/empty bodies, check params templates and column aliases.

When a **[Binding diagnosis]** block is attached to the user message, treat it as authoritative runtime contract analysis — lead with those findings.

## Host capabilities
- {upload_rule}

## Node palette (live)
{nodes_block}

## Data source schemas
{schema_hints}

## Skills library (reference)
{skills[:6000]}

Respond in clear markdown. Be concise, practical, and specific to the user's canvas/errors when provided.
"""
        return base + NEXT_ACTION_PROMPT

    # ── per-turn prompts ------------------------------------------------------
    def initial_prompt(
        self,
        scenario: str,
        current_workflow: dict[str, Any] | None = None,
        recent_errors: list[dict[str, Any]] | None = None,
        selected_node_id: str | None = None,
        matched_skills: list[str] | None = None,
        thread_context: str | None = None,
        planning_monologue: str | None = None,
    ) -> str:
        """Build the first user turn.

        Two modes:

        * **Greenfield** — no `current_workflow`. Wraps the scenario with
          a short creation brief so every generation turn explicitly points
          back at the live node contracts, data-source schemas, and matched
          skills from the system prompt.

        * **Edit-existing** — `current_workflow` is present. We embed
          the current DAG JSON and a normalised list of recent
          failures (validator issues, runtime exceptions, whatever the
          frontend attached), then hand the user's natural-language
          request as the delta to apply. The LLM is instructed to
          preserve node IDs and existing structure where possible so
          downstream tooling (node selection, run log, saved layout)
          doesn't get shuffled by an unrelated rewrite.

          `selected_node_id` lets deictic references in the request
          ("remove this", "change this threshold") resolve to a
          concrete node on the canvas rather than guessing.
        """
        context_block = _render_generation_context(
            matched_skills or self.match_skills(scenario)
        )
        thread_block = _render_thread_context(thread_context)
        planning_block = _render_planning_monologue(planning_monologue)

        if current_workflow is None:
            user_request = scenario.strip()
            return (
                "Create a NEW workflow from the user request below.\n"
                "\n"
                f"{thread_block}"
                f"{planning_block}"
                f"{context_block}"
                "## User request\n"
                f"{user_request}\n"
                "\n"
                "## Generation checklist\n"
                "- Build executable topology first, then artifacts requested by the user.\n"
                "- Keep graph minimal but complete; no placeholder/no-op branches for required outputs.\n"
                "- For artifact asks, ensure final writer path is concrete and deterministic.\n"
                "- If the request says merge/combine, include `data_merge` or `join` in the execution path.\n"
                "- If the request says split/branch/route, include `condition` or `router`.\n"
                "- For public sample company APIs, use `https://jsonplaceholder.typicode.com/users`.\n"
                "- Prefer declarative transform nodes over `code`.\n"
                "- If using `code`, write Starlark only (no Python syntax), add `code_summary`, write beautifully formatted and indented multiline code (4 spaces indentation), and comment every single logical step with inline `#` comments explaining what the logic is doing.\n"
                "- End CSV/Excel asks with `csv_output` or `excel_output`.\n"
                "- Return COMPLETE workflow JSON only.\n"
                "- Do not emit `note` nodes; use workflow description or node labels for setup hints.\n"
            )

        # Compact the DAG so the prompt stays within token budget for
        # large workflows. We drop UI-only fields (position, disabled)
        # but keep IDs/types/labels/configs/edges — those are what the
        # LLM needs to reason about a fix.
        compact = _compact_workflow(current_workflow)
        compact_json = json.dumps(compact, indent=2, default=str)

        error_block = _render_errors(recent_errors or [])
        selection_block = _render_selection(selected_node_id, current_workflow)
        user_request = scenario.strip() or "Fix the errors above."
        canvas_types = {
            str(n.get("type") or "").lower()
            for n in (current_workflow.get("nodes") or [])
            if isinstance(n, dict)
        }
        removal_guard = ""
        if (
            is_agent_visible_type("outlook")
            and "outlook" in user_request.lower()
            and "outlook" not in canvas_types
        ):
            removal_guard = (
                "- The canvas has **no Outlook nodes** (the user removed them). "
                "Do **not** add Outlook nodes unless the user explicitly asks to add Outlook now.\n"
            )

        return (
            "You are editing an EXISTING workflow that is already loaded in the canvas.\n"
            "\n"
            f"{thread_block}"
            f"{planning_block}"
            f"{context_block}"
            "## Current workflow (source of truth — do not recreate from scratch)\n"
            "```json\n"
            f"{compact_json}\n"
            "```\n"
            "\n"
            f"{error_block}"
            f"{selection_block}"
            "## User request\n"
            f"{user_request}\n"
            "\n"
            "## Editing rules\n"
            f"{removal_guard}"
            "- Preserve existing node IDs (`n01`, `n02`, …) and labels "
            "  wherever the node is still needed. Renaming IDs churns "
            "  the canvas and breaks the run log.\n"
            "- Make the smallest executable change set that satisfies request/errors.\n"
            "- Keep existing behavior intact unless user asked otherwise.\n"
            "- If the user uses deictic references (\"this\", \"that "
            "  node\", \"here\") and a node is listed under \"Currently "
            "  selected node\", treat that as the referent.\n"
            "- When inserting a new node between two existing nodes, "
            "  re-wire edges so the new node sits on the original path; "
            "  do not leave orphan edges.\n"
            "- When deleting a node, remove every edge that references "
            "  it AND reconnect the upstream → downstream nodes directly "
            "  if that preserves the original intent (otherwise leave "
            "  them disconnected and rely on the validator to flag it).\n"
            "- Assign new nodes fresh IDs continuing the `nNN` sequence "
            "  (highest existing + 1, zero-padded). Do not reuse a "
            "  deleted node's ID.\n"
            "- If fix requires file artifacts, end with `CONVERT_TO_FILE` then "
            "  `READ_WRITE_FILES_FROM_DISK` using concrete path.\n"
            "- Return the COMPLETE corrected workflow JSON (not a diff), "
            "  following the same schema as the Output Format in the "
            "  system prompt.\n"
        )

    def repair_prompt(
        self,
        errors: list[dict],
        attempt: int,
        total: int,
        *,
        planning_monologue: str | None = None,
    ) -> str:
        planning_block = _render_planning_monologue(planning_monologue)
        context_block = (
            planning_block
            + "Before repairing, re-check the current Node I/O Contracts, Data "
            "Source Column Schemas, and Surveillance Skills Library from the "
            "system prompt. "
            "Fix refs, config keys, node types, and columns against those current "
            "inventories only.\n\n"
        )
        starlark_block = _starlark_repair_block(errors)
        return context_block + starlark_block + build_feedback(errors, attempt, total)

    def last_step_snippet(self) -> str:
        return (
            "\n\n[FINAL STEP]\n"
            "This is the final allowed generation step. "
            "Return your best complete workflow JSON now, then stop."
        )

    def _provider_overlay(self, provider: str) -> str:
        if provider == "gemini":
            return "## Provider overlay\n- Favor strict JSON with deterministic field ordering."
        if provider == "claude":
            return "## Provider overlay\n- Keep output concise and avoid speculative extra keys."
        if provider == "openai":
            return "## Provider overlay\n- Prefer compact JSON and avoid redundant narration."
        return "## Provider overlay\n- Provider-agnostic strict JSON mode."

    def _role_overlay(self) -> str:
        return "## Role overlay\n- Operate as a workflow compiler with validation-first behavior."

    def _guardrail_slice(self, targets: list[str], guardrails: str) -> str:
        return (
            "## Guardrail slice\n"
            f"Node-targeted guardrails selected for this request: {targets or ['(none inferred; using global guardrails)']}\n"
            f"{guardrails}"
        )

    def _instruction_slice(self) -> str:
        instructions = self.instruction_resolver.resolve()
        if not instructions:
            return ""
        return "## Instruction slice\n" + "\n\n".join(instructions)

    def _skill_slice(self, skills: str) -> str:
        return f"## Skill slice\n{skills}"


def _resolve_backend_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    backend_relative = Path(__file__).resolve().parents[1] / candidate
    return backend_relative if backend_relative.exists() else candidate


def _compact_workflow(wf: dict[str, Any]) -> dict[str, Any]:
    """
    Strip UI-only fields from a workflow before embedding in a prompt.

    Keeps everything semantically relevant to generation/editing —
    node IDs, types, labels, configs, edges, workflow metadata —
    and drops things that only matter to the canvas (position,
    disabled flag). This keeps the prompt tight on large DAGs.
    """
    keep_top = {"workflow_id", "name", "description", "schema_version"}
    out: dict[str, Any] = {k: v for k, v in wf.items() if k in keep_top}
    out["nodes"] = [
        {k: v for k, v in node.items() if k not in ("position", "disabled")}
        for node in wf.get("nodes", [])
    ]
    out["edges"] = [
        {"from": e.get("from"), "to": e.get("to")} for e in wf.get("edges", [])
    ]
    return out


def _render_planning_monologue(planning_monologue: str | None) -> str:
    text = (planning_monologue or "").strip()
    if not text:
        return ""
    return (
        "## Sherpa planning (binding — the next generation step MUST follow this)\n"
        f"{text}\n"
        "\n"
    )


def _render_thread_context(thread_context: str | None) -> str:
    text = (thread_context or "").strip()
    if not text:
        return ""
    return (
        "## Recent conversation in this thread\n"
        "Use this for follow-ups, pronouns, and references to earlier turns.\n"
        "The canvas snapshot below (if any) reflects what is loaded now.\n"
        f"{text}\n"
        "\n"
    )


def _render_generation_context(matched_skills: list[str] | None) -> str:
    skills = matched_skills or []
    skill_text = ", ".join(f"`{s}`" for s in skills) if skills else "(none)"
    return (
        "## Current generation context\n"
        "- Node definitions: use the live registry-backed Node I/O Contracts "
        "in the system prompt.\n"
        "- Data sources: use the live data-source registry schemas in the "
        "system prompt.\n"
        f"- Matched/on-demand skills: {skill_text}.\n"
        "\n"
    )


def _render_selection(
    selected_node_id: str | None,
    workflow: dict[str, Any],
) -> str:
    """
    Emit a short block naming the selected node so deictic references
    in the user's request ("this", "here", "remove that node") map
    to a concrete ID. Falls back silently if the ID doesn't resolve
    — the frontend may have stale state relative to the DAG we just
    sent, and we don't want to block the edit on a mismatch.
    """
    if not selected_node_id:
        return ""
    match = next(
        (n for n in workflow.get("nodes", []) if n.get("id") == selected_node_id),
        None,
    )
    if not match:
        return ""
    label = match.get("label") or match.get("id")
    type_ = match.get("type") or "?"
    return (
        "## Currently selected node (what \"this\" / \"that node\" refers to)\n"
        f"- `{match.get('id')}` · **{type_}** · {label}\n"
        "\n"
    )


def _render_errors(errors: list[dict[str, Any]]) -> str:
    """
    Normalise a mixed list of validator issues / runtime exceptions /
    free-form error strings into a single bulleted section the LLM
    can act on.

    Each item is expected to be a dict with at least one of:
      * `code` — validator error code (e.g. `UNKNOWN_NODE_TYPE`)
      * `node_id` — id of the offending node
      * `message` — human-readable description
      * `severity` — "error" | "warning" | "info"
      * `kind` — "validation" | "runtime" (optional hint)

    We accept plain strings too — they're wrapped as `{"message": str}`
    so the caller doesn't have to pre-shape them.
    """
    if not errors:
        return ""
    lines = ["## Recent errors to fix"]
    for raw in errors:
        if isinstance(raw, str):
            raw = {"message": raw}
        code = raw.get("code")
        node_id = raw.get("node_id") or raw.get("nodeId")
        severity = (raw.get("severity") or "error").upper()
        kind = raw.get("kind")
        message = raw.get("message") or raw.get("detail") or "(no details)"
        prefix_bits = [severity]
        if kind:
            prefix_bits.append(kind)
        if code:
            prefix_bits.append(f"code={code}")
        if node_id:
            prefix_bits.append(f"node={node_id}")
        prefix = " ".join(prefix_bits)
        lines.append(f"- [{prefix}] {message}")
    lines.append("")  # blank line before next section
    return "\n".join(lines) + "\n"


def _starlark_repair_block(errors: list[dict[str, Any]]) -> str:
    """Emit an explicit Starlark rewrite recipe when error payload implies code-node parse failures."""
    if not errors:
        return ""
    haystack_parts: list[str] = []
    for err in errors:
        if isinstance(err, str):
            haystack_parts.append(err)
            continue
        if isinstance(err, dict):
            haystack_parts.append(str(err.get("code") or ""))
            haystack_parts.append(str(err.get("field") or ""))
            haystack_parts.append(str(err.get("message") or err.get("detail") or ""))
    haystack = " ".join(haystack_parts).lower()
    triggers = (
        "starlark",
        "workflow_code.starlark",
        "code is not valid starlark",
        "cannot be used outside `def`",
        "cannot be used outside def",
        "config.code",
    )
    if not any(t in haystack for t in triggers):
        return ""
    return (
        "## Starlark repair recipe (mandatory for code-node errors)\n"
        "- Rewrite `config.code` in Starlark dialect only.\n"
        "- Never leave executable control flow (`if`, `for`) at top level.\n"
        "- Wrap logic inside a function, e.g. `def transform(rows): ...`.\n"
        "- Call the function with `input_data[\"rows\"]`.\n"
        "- Assign final output with `output = transform(input_data[\"rows\"])`.\n"
        "- Do not use Python-only constructs (`import`, `try/except`, `class`).\n"
        "- Never reference undeclared globals (`workflow_run_id`, `run_id`, `_passed`).\n"
        "- Evaluator forwards passed rows only; use `_eval` or `len(input_data[\"rows\"])`, not `_passed`.\n"
        "- Write beautifully formatted and indented multiline code (4 spaces indentation) and include inline `#` comments at every single step explaining the operations.\n"
        "- Preserve the intent and output schema of the failing node; change only syntax/structure needed to compile.\n\n"
    )
