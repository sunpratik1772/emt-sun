"""Prompt enhancer layer for Copilot generation.

Transforms free-form user prompts into a richer, structured objective block
that downstream planners/compilers can consume deterministically.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from engine.mcp_nodes import active_mcp_node_types


@dataclass
class EnhancedPrompt:
    raw_prompt: str
    enhanced_prompt: str
    profile: dict[str, Any]


class PromptEnhancer:
    """Deterministic prompt-to-requirements mapper."""

    def enhance(self, prompt: str) -> EnhancedPrompt:
        text = (prompt or "").strip()
        lc = text.lower()

        artifacts: list[str] = []
        if any(k in lc for k in ("excel", "xlsx", "xls", "spreadsheet", "workbook")):
            artifacts.append("excel_or_sheet")
        if "csv" in lc:
            artifacts.append("csv")
        if any(k in lc for k in ("markdown", ".md", "md report")):
            artifacts.append("markdown")
        if "json" in lc:
            artifacts.append("json")
        if "pdf" in lc:
            artifacts.append("pdf")
        if any(k in lc for k in ("email", "mail draft", "email draft")):
            artifacts.append("email_draft")
        if any(k in lc for k in ("artifact", "artifacts", "save to disk", "write to file", "output file")):
            artifacts.append("file_artifact")

        requires_loop = any(k in lc for k in ("loop", "iterate", "batch", "for each", "split in batches"))
        requires_merge = any(k in lc for k in ("merge", "join", "combine"))
        requires_branching = any(k in lc for k in ("if ", "switch", "route", "branch"))
        llm_calls = 2 if any(k in lc for k in ("multiple gemini", "multiple llm", "two gemini", "two llm")) else (1 if any(k in lc for k in ("gemini", "llm")) else 0)

        popular_domain = self._infer_domain(lc)
        complexity = self._infer_complexity(text, lc)
        layer1_breakdown = self._layer1_breakdown(text, lc, {
            "domain": popular_domain,
            "requires_loop": requires_loop,
            "requires_merge": requires_merge,
            "requires_branching": requires_branching,
        })
        structured_plan = self._layer1_structured_plan(text, layer1_breakdown)

        profile = {
            "domain": popular_domain,
            "complexity": complexity,
            "required_artifacts": sorted(set(artifacts)),
            "requires_loop": requires_loop,
            "requires_merge": requires_merge,
            "requires_branching": requires_branching,
            "min_llm_calls": llm_calls,
            "layer1_breakdown": layer1_breakdown,
            "layer1_structured_plan": structured_plan,
        }

        enhanced = self._render_enhanced_prompt(text, profile)
        return EnhancedPrompt(raw_prompt=text, enhanced_prompt=enhanced, profile=profile)

    def _infer_domain(self, lc: str) -> str:
        mapping = {
            "support": "support_ops",
            "incident": "incident_response",
            "ticket": "support_ops",
            "revops": "revenue_ops",
            "lead": "revenue_ops",
            "campaign": "marketing_ops",
            "research": "content_ops",
            "content": "content_ops",
            "finops": "finance_ops",
            "billing": "finance_ops",
        }
        for key, domain in mapping.items():
            if key in lc:
                return domain
        return "general_automation"

    def _infer_complexity(self, text: str, lc: str) -> str:
        hard_markers = (
            "difficult",
            "complex",
            "multi",
            "parallel",
            "loop",
            "merge",
            "branch",
            "orchestrate",
        )
        score = sum(1 for k in hard_markers if k in lc)
        score += 1 if len(re.findall(r"\n", text)) >= 3 else 0
        if score >= 5:
            return "hard"
        if score >= 3:
            return "medium"
        return "simple"

    def _render_enhanced_prompt(self, raw: str, profile: dict[str, Any]) -> str:
        breakdown = profile.get("layer1_breakdown") or {}
        structured_plan = profile.get("layer1_structured_plan") or {}
        decomposition_lines = [
            f"- normalized_intent: {breakdown.get('normalized_intent', 'general workflow')}",
            f"- mandatory_capabilities: {breakdown.get('mandatory_capabilities', [])}",
            f"- fixed_execution_shape: {breakdown.get('fixed_execution_shape', [])}",
            f"- deterministic_artifacts: {breakdown.get('deterministic_artifacts', [])}",
            f"- code_safety_contract: {breakdown.get('code_safety_contract', [])}",
            f"- node_config_contract: {breakdown.get('node_config_contract', [])}",
            f"- lineage_contract: {breakdown.get('lineage_contract', [])}",
            f"- canonical_required_fields: {breakdown.get('canonical_required_fields', [])}",
            f"- count_contract: {breakdown.get('count_contract', [])}",
            f"- summary_text_contract: {breakdown.get('summary_text_contract', [])}",
            f"- semantic_checks: {breakdown.get('semantic_checks', [])}",
        ]

        lines = [
            "User objective:",
            raw,
            "",
            "Compiler requirements (auto-mapped):",
            f"- domain: {profile['domain']}",
            f"- complexity: {profile['complexity']}",
            f"- required_artifacts: {profile['required_artifacts']}",
            f"- requires_loop: {profile['requires_loop']}",
            f"- requires_merge: {profile['requires_merge']}",
            f"- requires_branching: {profile['requires_branching']}",
            f"- minimum_llm_calls: {profile['min_llm_calls']}",
            "",
            "Compilation policy:",
            "- Prefer nodes that satisfy required_artifacts explicitly.",
            "- Ensure final artifact-producing file outputs when required_artifacts is non-empty.",
            "- Avoid NO_OP for any mandatory artifact branch.",
            "- Keep DAG acyclic and execution-safe.",
            "",
            "Layer 1 decomposition (auto-expanded from natural prompt):",
            *decomposition_lines,
            "",
            "Layer 1 structured output (must drive emitted node plan):",
            json.dumps(structured_plan, indent=2, sort_keys=True),
            "",
            "Layer 1 before/after example (natural -> execution-ready):",
            "Before (natural): Build a data hygiene workflow with dedupe, key normalization, and cleaned JSON + markdown outputs.",
            "After (decomposed):",
            "- mandatory_capabilities: ['seed deterministic mock rows','deduplicate entities','normalize key names','parse nested payloads','shape list fields','emit canonical records','write deterministic artifacts']",
            "- fixed_execution_shape: ['seed->dedupe->normalize->canonicalize->artifact writers','separate summary branch computes before_count/after_count']",
            "- deterministic_artifacts: ['/tmp/<variant_id>_cleaned.json','/tmp/<variant_id>_schema_summary.md']",
            "- code_safety_contract: ['language=python','use .get(...) access only','no dict(item)','no item.copy()','no proxy membership probes']",
            "- node_config_contract: ['all selected nodes must use runtime-supported config schema','no ad-hoc unsupported assignment forms','field-targeted operations must reference fields that exist at that stage','inline expressions should stay projection/arithmetic-safe (no method-call chains on unresolved paths)','typed transform parameters must resolve to concrete runtime values (no unresolved template literals)']",
            "- lineage_contract: ['if a key is renamed, downstream references must use renamed key exactly','no references to non-existent parent objects']",
            "- canonical_required_fields: ['id','full_name','email','company','region']",
            "- count_contract: ['before_count must come from pre-dedupe branch','after_count must come from canonical post-dedupe rows','after_count <= before_count']",
            "- summary_text_contract: ['markdown must include literal lines: - before_count: <n> and - after_count: <n>']",
        ]
        return "\n".join(lines)

    def _layer1_structured_plan(self, text: str, breakdown: dict[str, Any]) -> dict[str, Any]:
        """Emit machine-readable Layer 1 node plan from natural language."""
        caps = [str(x) for x in (breakdown.get("mandatory_capabilities") or [])]
        shape = [str(x) for x in (breakdown.get("fixed_execution_shape") or [])]
        artifacts = [str(x) for x in (breakdown.get("deterministic_artifacts") or [])]
        summary_checks = [str(x) for x in (breakdown.get("summary_text_contract") or [])]

        node_set: set[str] = {"manual_trigger"}

        cap_text = " ".join(caps).lower()
        shape_text = " ".join(shape).lower()
        all_text = f"{cap_text} {shape_text} {text.lower()}"

        if any(k in all_text for k in ("deduplicate", "data hygiene", "rename key", "canonical")):
            node_set.update({"code", "deduplicate", "map_transform", "csv_output"})

        if any(k in all_text for k in ("compare", "delta", "baseline", "severity", "kpi")):
            node_set.update({
                "code",
                "filter",
                "condition",
                "router",
                "loop",
                "group_by",
                "data_merge",
                "sort",
                "agent",
                "csv_output",
                "excel_output",
            })

        if any(k in all_text for k in ("markdown", ".md", "summary")):
            node_set.update({"agent", "csv_output"})
        if any(k in all_text for k in ("workbook", "xlsx", "spreadsheet")):
            node_set.add("excel_output")
        if any(k in all_text for k in ("confluence", "jira", "mcp")):
            node_set.update(active_mcp_node_types())
        if "github" in all_text and (
            "activity" in all_text
            or any(k in all_text for k in ("commit", "commits", "repo", "briefing"))
        ):
            node_set.update({"github_mcp", "agent", "confluence_mcp"})
        elif "github" in all_text:
            node_set.add("github_mcp")

        return {
            "version": "1.0",
            "normalized_objective": text.split("\n", 1)[0][:220] if text else "build deterministic workflow",
            "mandatory_nodes": sorted(node_set),
            "node_emission_policy": {
                "require_all_mandatory_nodes": True,
                "allow_extra_nodes_only_if_contract_backed": True,
                "forbid_unlisted_node_types_without_objective_need": True,
            },
            "guardrail_fetch_policy": {
                "fetch_node_specific_guardrails_for": sorted(node_set),
                "also_include_global_runtime_rules": True,
            },
            "artifacts": artifacts,
            "summary_contract": summary_checks,
        }

    def _layer1_breakdown(self, text: str, lc: str, hints: dict[str, Any]) -> dict[str, Any]:
        capabilities: list[str] = []
        execution_shape: list[str] = []
        artifacts: list[str] = []
        semantic: list[str] = []
        code_contract: list[str] = []
        node_config_contract: list[str] = []
        lineage_contract: list[str] = []
        canonical_required_fields: list[str] = []
        count_contract: list[str] = []
        summary_contract: list[str] = []

        # Data-hygiene style natural language decomposition
        data_hygiene_markers = (
            "deduplicate" in lc
            or "remove duplicates" in lc
            or "rename fields" in lc
            or "key names" in lc
            or "schema summary" in lc
        )
        compare_delta_markers = (
            ("compare" in lc or "delta" in lc)
            and ("baseline" in lc or "kpi" in lc or "severity" in lc)
            and ("switch" in lc or "batch" in lc or "loop" in lc)
        )
        if data_hygiene_markers:
            capabilities = [
                "seed deterministic mock rows",
                "deduplicate entities",
                "normalize key names",
                "parse nested payloads",
                "shape list fields",
                "emit canonical records",
                "write deterministic artifacts",
            ]
            execution_shape = [
                "seed->dedupe->normalize->canonicalize->artifact writers",
                "separate summary branch computes before_count/after_count",
            ]
            artifacts = [
                "/tmp/<variant_id>_cleaned.json",
                "/tmp/<variant_id>_schema_summary.md",
            ]
            semantic = [
                "cleaned JSON exists and non-empty",
                "summary markdown exists and non-empty",
                "summary mentions before_count and after_count",
                "no [LLM error ...] marker",
                "no unresolved template markers",
                "node configs conform to runtime-supported shapes",
                "canonical required fields are present in output rows",
                "critical nested extracts expected by objective are non-null when source contains values",
                "after_count <= before_count",
            ]
            node_config_contract = [
                "all selected nodes must use runtime-supported config schema",
                "field-targeted operations must reference fields that exist at that stage",
                "when before/after counts are required, summary branch must receive both pre and post datasets explicitly",
                "avoid unsupported ad-hoc config forms",
                "inline expressions should stay projection/arithmetic-safe and avoid method-call chains on unresolved paths",
                "typed transform parameters must resolve to concrete runtime values and avoid unresolved template literals",
            ]
            canonical_required_fields = [
                "id",
                "full_name",
                "email",
                "company",
                "region",
            ]
            lineage_contract = [
                "if a key is renamed, downstream references must use renamed key",
                "all field path references must match keys available at that stage",
                "expressions must not reference non-existent parent objects",
            ]
            count_contract = [
                "before_count sourced from pre-dedupe branch",
                "after_count sourced from post-dedupe canonical rows",
                "after_count <= before_count",
            ]
            summary_contract = [
                "markdown must include literal key lines",
                "line format: - before_count: <n>",
                "line format: - after_count: <n>",
            ]
            code_contract = [
                "language=python",
                "use .get(...) access only",
                "avoid dict(item)",
                "avoid item.copy()",
                "avoid proxy membership probes",
            ]
        elif compare_delta_markers:
            capabilities = [
                "seed deterministic event rows",
                "normalize timestamp fields",
                "route by branch keys",
                "batch/loop branch processing",
                "aggregate and compare processed vs baseline metrics",
                "emit ranked delta outputs",
                "write deterministic workbook and markdown artifacts",
            ]
            execution_shape = [
                "seed->time normalize->switch/branch->batch/loop->summarize/aggregate->compare->delta normalize->artifact writers",
                "comparison branch must preserve processed/baseline lineage into delta rows",
                "markdown summary branch must consume normalized delta rows (not pre-compare placeholders)",
            ]
            artifacts = [
                "/tmp/<variant_id>_kpi_deltas.xlsx",
                "/tmp/<variant_id>_findings.md",
            ]
            semantic = [
                "workbook artifact exists and non-empty",
                "markdown artifact exists and non-empty",
                "markdown includes delta narrative and top findings",
                "no [LLM error ...] marker",
                "no unresolved template markers",
                "processed branch emits non-empty KPI rows before compare",
                "baseline branch emits non-empty KPI rows before compare",
                "compare rows exist and have non-null grouping keys",
                "delta rows are not all zero when baseline/processed sources are intentionally different",
            ]
            node_config_contract = [
                "all selected nodes must use runtime-supported config schema",
                "field-targeted operations must reference fields that exist at that stage",
                "multi-input compare/merge nodes must wire explicit input1/input2 branches",
                "if delta code expects paired compare payloads, compare resolve mode must emit paired rows (inputA/inputB or input1/input2)",
                "MERGE matching-fields config must use valid field-name lists (not unsupported object-only shapes)",
                "normalize processed/baseline metric field names before delta calculation",
                "FILTER conditions must use runtime-supported operators only",
                "IF conditions using item-count checks must use runtime-resolvable numeric expressions",
                "delta code must read compare rows using the actual runtime row shape (no hardcoded wrapper assumptions)",
                "delta normalization step is mandatory before workbook/markdown writers",
                "branch filters/routing must not collapse all rows before aggregation unless objective explicitly requests empty output",
                "LLM prompt templates must use runtime-resolvable placeholders only (for example {{ $json }} or {{ JSON.stringify($items) }})",
                "avoid JS-method placeholders in templates (for example $items.slice(...) or $json.to_json) unless upstream creates that exact field/text",
                "if seed step emits arrays (for example processed_data/baseline_data), add an explicit row-expansion step before SWITCH/FILTER/SUMMARIZE",
                "wire COMPARE_DATASETS directly from processed aggregate branch to input1 and baseline aggregate branch to input2 (do not pre-merge branches into one stream before compare)",
                "LLM markdown-summary prompts for compare objectives must explicitly request delta/drift wording and ranking cues in final text",
                "FILTER/SWITCH/IF expression templates must use one runtime-resolvable form only (for example ={{ $json.severity }}), never nested/mixed template strings",
                "for workbook artifacts, prefer SPREADSHEET_FILE write node as terminal writer; do not add CONVERT_TO_FILE-toBinary tails after spreadsheet write unless objective explicitly requires binary re-encoding",
            ]
            canonical_required_fields = [
                "severity",
                "region",
                "processed_count",
                "baseline_count",
                "delta",
            ]
            lineage_contract = [
                "comparison keys must align across processed and baseline branches",
                "downstream delta code must read actual compare output shape emitted by runtime",
                "compare output shape and delta-code access pattern must match exactly (paired vs flattened)",
                "metric aliases must be normalized before sorting/ranking outputs",
                "processed and baseline branches must be independently traceable into compare inputs",
                "if rows are wrapped under json envelope, key extraction and compare mapping must still resolve canonical fields",
            ]
            count_contract = [
                "processed_count sourced from post-branch aggregations",
                "baseline_count sourced from baseline branch",
                "delta = processed_count - baseline_count",
            ]
            summary_contract = [
                "markdown must include explicit delta findings",
                "markdown must include top-delta section",
                "markdown must contain literal keyword 'delta' and one ranking marker (top/most significant/rank/highest)",
                "markdown input must be derived from normalized delta rows with non-null grouping keys",
                "markdown must not contain unresolved moustache/template markers",
            ]
            code_contract = [
                "language=python",
                "use .get(...) access only",
                "avoid dict(item)",
                "avoid item.copy()",
                "avoid proxy membership probes",
            ]
        else:
            if "json" in lc:
                artifacts.append("json output required")
            if "markdown" in lc or ".md" in lc:
                artifacts.append("markdown output required")
            semantic = [
                "artifacts exist",
                "artifacts non-empty",
                "no unresolved templates",
            ]

        return {
            "normalized_intent": text.split("\n", 1)[0][:220] if text else "build deterministic workflow",
            "mandatory_capabilities": capabilities,
            "fixed_execution_shape": execution_shape,
            "deterministic_artifacts": artifacts,
            "code_safety_contract": code_contract,
            "node_config_contract": node_config_contract,
            "lineage_contract": lineage_contract,
            "canonical_required_fields": canonical_required_fields,
            "count_contract": count_contract,
            "summary_text_contract": summary_contract,
            "semantic_checks": semantic,
        }
