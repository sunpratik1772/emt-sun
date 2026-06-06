"""Strict multi-agent LLM-to-DAG compiler.

Implements a staged compiler pipeline:
1) semantic node selection
2) topology generation
3) per-node parameterization with lineage checks
4) strict schema validation + self-healing correction loop
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from engine.dag_runner import topological_sort
from engine.registry import NODE_SPECS
from engine.validator import validate_dag
from llm import GeminiAdapter, get_default_adapter


_TRIGGER_TYPES = {
    "MANUAL_TRIGGER",
    "WEBHOOK",
    "SCHEDULE_TRIGGER",
    "CHAT_TRIGGER",
    "FORM_TRIGGER",
    "N8N_TRIGGER",
    "WORKFLOW_TRIGGER",
    "ACTIVATION_TRIGGER",
    "MCP_SERVER_TRIGGER",
    "SSE_TRIGGER",
    "ERROR_TRIGGER",
    "EMAIL_TRIGGER_IMAP",
    "RSS_FEED_TRIGGER",
    "EVALUATION_TRIGGER",
    "EXECUTE_WORKFLOW_TRIGGER",
    "LOCAL_FILE_TRIGGER",
}
_TEMPLATE_REF = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*\}\}")


class _TopologyEdge(BaseModel):
    source: str
    target: str


class _TopologyPayload(BaseModel):
    edges: List[_TopologyEdge] = Field(default_factory=list)


class _NodePayload(BaseModel):
    node_id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class StrictCompileResult:
    success: bool
    workflow: Optional[dict]
    error: Optional[str]
    diagnostics: dict[str, Any]


class StrictDAGCompiler:
    """LLM compiler with explicit deterministic checkpoints."""

    def __init__(self, llm: Optional[GeminiAdapter] = None) -> None:
        self._llm = llm or get_default_adapter()

    def compile(self, objective: str, *, max_corrections: int = 3) -> StrictCompileResult:
        diagnostics: dict[str, Any] = {"layers": {}}

        # Layer 1: semantic retrieval / node selection.
        selected, err = self._layer_select_nodes(objective, max_corrections=max_corrections)
        diagnostics["layers"]["selection"] = {"selected_nodes": selected, "error": err}
        if err or not selected:
            return StrictCompileResult(False, None, err or "No nodes selected", diagnostics)

        # Layer 2: topology.
        edges, err = self._layer_topology(objective, selected, max_corrections=max_corrections)
        diagnostics["layers"]["topology"] = {
            "edges": [{"source": e["from"], "target": e["to"]} for e in edges],
            "error": err,
        }
        if err:
            return StrictCompileResult(False, None, err, diagnostics)

        selected, edges = self._inject_trigger_if_missing(selected, edges)
        diagnostics["layers"]["topology"]["selected_nodes_after_trigger_guard"] = selected

        # Layer 3: parameterization.
        node_payloads, err = self._layer_parameterize(objective, selected, edges, max_corrections=max_corrections)
        diagnostics["layers"]["parameterization"] = {
            "nodes": node_payloads,
            "error": err,
        }
        if err:
            return StrictCompileResult(False, None, err, diagnostics)

        wf = self._assemble_workflow(objective, selected, edges, node_payloads)

        # Layer 4: strict schema/validation + repair loop.
        repaired, validation, err = self._layer_validate_and_repair(
            objective, wf, max_corrections=max_corrections
        )
        diagnostics["layers"]["validation"] = {
            "valid": validation.get("valid", False),
            "summary": validation.get("summary"),
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "error": err,
        }
        if err:
            return StrictCompileResult(False, repaired, err, diagnostics)

        return StrictCompileResult(True, repaired, None, diagnostics)

    # ------------------------- Layer 1 ---------------------------------
    def _layer_select_nodes(self, objective: str, *, max_corrections: int) -> tuple[list[str], Optional[str]]:
        index = self._registry_index()
        system = (
            "You are an orchestration architect.\n"
            "Select required node IDs from Registry Index to satisfy the objective.\n"
            "Rules:\n"
            "1) Return ONLY JSON list of node IDs.\n"
            "2) Never invent IDs outside Registry Index.\n"
        )
        user = f"Objective:\n{objective}\n\nRegistry Index:\n{index}\n"
        invalid_reason = ""
        for _ in range(max(1, max_corrections)):
            payload, parse_err = self._ask_json(system, user)
            if parse_err:
                invalid_reason = parse_err
                user = f"{user}\nError: {parse_err}\nReturn only JSON array of node IDs."
                continue
            if not isinstance(payload, list):
                invalid_reason = "Expected JSON array of node IDs."
                user = f"{user}\nError: {invalid_reason}\nReturn only JSON array."
                continue
            selected = [str(x).strip() for x in payload if str(x).strip()]
            unknown = [n for n in selected if n not in NODE_SPECS]
            if unknown:
                invalid_reason = f"Unknown node IDs: {unknown}. Choose only from Registry Index."
                user = f"{user}\nError: {invalid_reason}\nReturn corrected JSON array."
                continue
            # dedupe while preserving order
            deduped: list[str] = []
            for n in selected:
                if n not in deduped:
                    deduped.append(n)
            return deduped, None
        return [], invalid_reason or "Node selection failed"

    # ------------------------- Layer 2 ---------------------------------
    def _layer_topology(
        self, objective: str, selected_nodes: list[str], *, max_corrections: int
    ) -> tuple[list[dict[str, str]], Optional[str]]:
        system = (
            "You are a DAG routing engine.\n"
            "Construct execution topology for selected nodes.\n"
            "Return ONLY JSON object: {\"edges\": [{\"source\": \"...\", \"target\": \"...\"}]}\n"
            "No cycles. No orphan nodes when more than one node selected.\n"
        )
        user = (
            f"Objective:\n{objective}\n\n"
            f"Selected Nodes:\n{json.dumps(selected_nodes)}\n"
        )
        invalid_reason = ""
        for _ in range(max(1, max_corrections)):
            payload, parse_err = self._ask_json(system, user)
            if parse_err:
                invalid_reason = parse_err
                user = f"{user}\nError: {parse_err}\nReturn strict edges JSON object."
                continue
            try:
                parsed = _TopologyPayload.model_validate(payload)
            except ValidationError as exc:
                invalid_reason = f"Topology schema invalid: {exc}"
                user = f"{user}\nError: {invalid_reason}\nReturn strict edges JSON object."
                continue

            raw_edges = [{"from": e.source, "to": e.target} for e in parsed.edges]
            edges, canon_err = self._canonicalize_edges(selected_nodes, raw_edges)
            if canon_err:
                invalid_reason = canon_err
                user = f"{user}\nError: {canon_err}\nUse only selected node IDs for endpoints."
                continue
            topology_error = self._validate_topology(selected_nodes, edges)
            if topology_error:
                invalid_reason = topology_error
                user = f"{user}\nError: {topology_error}\nRe-map edges with no cycles and no missing nodes."
                continue
            return edges, None
        return [], invalid_reason or "Topology generation failed"

    # ------------------------- Layer 3 ---------------------------------
    def _layer_parameterize(
        self,
        objective: str,
        selected_nodes: list[str],
        edges: list[dict[str, str]],
        *,
        max_corrections: int,
    ) -> tuple[dict[str, dict[str, Any]], Optional[str]]:
        order = topological_sort(
            [{"id": node_id} for node_id in selected_nodes],
            edges,
        )
        upstream_map: dict[str, list[str]] = {n: [] for n in selected_nodes}
        for edge in edges:
            upstream_map[edge["to"]].append(edge["from"])

        out: dict[str, dict[str, Any]] = {}
        for node_id in order:
            spec = NODE_SPECS[node_id]
            input_specs = [{"name": p.name, "type": p.type.value} for p in spec.input_ports]
            config_specs = [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "required": p.required,
                    "enum": list(p.enum or []),
                    "default": p.default,
                }
                for p in spec.params
            ]
            upstream = {
                u: [p.name for p in NODE_SPECS[u].output_ports]
                for u in upstream_map.get(node_id, [])
            }
            system = (
                "You are a parameterization agent.\n"
                "Return ONLY JSON object with keys: node_id, inputs, config.\n"
                "Use template syntax for upstream mappings: {{ source_node.output_key }}.\n"
                "Never reference future nodes. Only use listed upstream outputs.\n"
            )
            user = (
                f"Objective:\n{objective}\n\n"
                f"Node ID: {node_id}\n"
                f"Node Description: {spec.description}\n"
                f"Input Spec: {json.dumps(input_specs)}\n"
                f"Config Spec: {json.dumps(config_specs)}\n"
                f"Upstream Outputs: {json.dumps(upstream)}\n"
            )
            invalid_reason = ""
            payload_obj: Optional[_NodePayload] = None
            for _ in range(max(1, max_corrections)):
                payload, parse_err = self._ask_json(system, user)
                if parse_err:
                    invalid_reason = parse_err
                    user = f"{user}\nError: {parse_err}\nReturn strict JSON object."
                    continue
                try:
                    parsed = _NodePayload.model_validate(payload)
                except ValidationError as exc:
                    invalid_reason = f"Node payload schema invalid: {exc}"
                    user = f"{user}\nError: {invalid_reason}\nReturn strict JSON object."
                    continue
                if parsed.node_id != node_id:
                    invalid_reason = f"node_id mismatch. Expected '{node_id}', got '{parsed.node_id}'."
                    user = f"{user}\nError: {invalid_reason}\nReturn corrected JSON."
                    continue
                ref_err = self._validate_refs(
                    parsed.inputs, node_id=node_id, upstream_outputs=upstream
                )
                if ref_err:
                    invalid_reason = ref_err
                    user = f"{user}\nError: {ref_err}\nFix template mappings."
                    continue
                payload_obj = parsed
                break
            if payload_obj is None:
                return {}, f"Parameterization failed for node '{node_id}': {invalid_reason}"
            out[node_id] = {"inputs": payload_obj.inputs, "config": payload_obj.config}
        return out, None

    # ------------------------- Layer 4 ---------------------------------
    def _layer_validate_and_repair(
        self,
        objective: str,
        workflow: dict[str, Any],
        *,
        max_corrections: int,
    ) -> tuple[dict[str, Any], dict[str, Any], Optional[str]]:
        current = workflow
        validation = validate_dag(current).to_json()
        if validation.get("valid"):
            return current, validation, None

        system = (
            "You are a strict workflow corrector.\n"
            "Fix workflow JSON to satisfy deterministic schema validation.\n"
            "Return ONLY complete corrected workflow JSON.\n"
            "Do not add unknown node types.\n"
        )
        for attempt in range(max(1, max_corrections)):
            user = (
                f"Objective:\n{objective}\n\n"
                f"Validation summary:\n{validation.get('summary')}\n"
                f"Validation errors:\n{json.dumps(validation.get('errors', []), indent=2)}\n\n"
                f"Invalid workflow JSON:\n{json.dumps(current, indent=2)}\n\n"
                "Fix and return full workflow JSON."
            )
            payload, parse_err = self._ask_json(system, user)
            if parse_err:
                continue
            if not isinstance(payload, dict):
                continue
            current = payload
            validation = validate_dag(current).to_json()
            if validation.get("valid"):
                return current, validation, None
            if attempt == max_corrections - 1:
                return current, validation, f"Validation failed after {max_corrections} correction attempts"
        return current, validation, "Validation failed"

    # ------------------------- Build -----------------------------------
    def _assemble_workflow(
        self,
        objective: str,
        selected_nodes: list[str],
        edges: list[dict[str, str]],
        node_payloads: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        order = topological_sort([{"id": n} for n in selected_nodes], edges)
        id_map = {type_id: f"n{idx + 1:02d}" for idx, type_id in enumerate(order)}
        nodes_out: list[dict[str, Any]] = []
        for type_id in order:
            payload = node_payloads.get(type_id, {})
            cfg = dict(payload.get("config") or {})
            # Keep inputs explicit for deterministic wiring introspection.
            if payload.get("inputs"):
                cfg["inputs"] = payload["inputs"]
            nodes_out.append(
                {
                    "id": id_map[type_id],
                    "type": type_id,
                    "label": type_id.replace("_", " ").title(),
                    "config": cfg,
                }
            )
        edges_out = [{"from": id_map[e["from"]], "to": id_map[e["to"]]} for e in edges]
        slug = re.sub(r"[^a-z0-9]+", "_", objective.lower()).strip("_")[:60] or "compiled_workflow"
        workflow = {
            "workflow_id": f"wf_{slug}",
            "name": f"Compiled: {objective[:60]}",
            "schema_version": "1.0",
            "description": "Workflow compiled via strict multi-agent pipeline.",
            "nodes": nodes_out,
            "edges": edges_out,
        }
        workflow = self._inject_artifact_tail_if_needed(workflow, objective)
        return self._materialize_artifact_paths(workflow)

    # ------------------------- Helpers ---------------------------------
    def _registry_index(self) -> str:
        rows = []
        for node_id, spec in sorted(NODE_SPECS.items()):
            rows.append(f"- id: {node_id} | desc: {spec.description}")
        return "\n".join(rows)

    def _ask_json(self, system_prompt: str, user_turn: str) -> tuple[Any, Optional[str]]:
        text = self._llm.chat_turn(
            system_prompt=system_prompt,
            history=[],
            user_turn=user_turn,
            temperature=0.0,
            json_mode=True,
        )
        try:
            return json.loads(text), None
        except Exception:
            block = self._extract_json_block(text)
            if block is None:
                return None, "Model output is not parseable JSON."
            try:
                return json.loads(block), None
            except Exception as exc:
                return None, f"JSON parse error: {exc}"

    def _extract_json_block(self, text: str) -> Optional[str]:
        if not text:
            return None
        obj = re.search(r"\{[\s\S]*\}", text)
        arr = re.search(r"\[[\s\S]*\]", text)
        if obj and arr:
            return obj.group(0) if obj.start() < arr.start() else arr.group(0)
        if obj:
            return obj.group(0)
        if arr:
            return arr.group(0)
        return None

    def _validate_topology(self, selected_nodes: list[str], edges: list[dict[str, str]]) -> Optional[str]:
        selected = set(selected_nodes)
        for edge in edges:
            src = edge.get("from")
            dst = edge.get("to")
            if src not in selected or dst not in selected:
                return f"Edge contains unknown endpoint: {edge}"
        try:
            topological_sort([{"id": n} for n in selected_nodes], edges)
        except Exception as exc:
            return f"Topological cycle detected or invalid DAG: {exc}"
        if len(selected_nodes) > 1:
            touched = {e["from"] for e in edges} | {e["to"] for e in edges}
            missing = [n for n in selected_nodes if n not in touched]
            if missing:
                return f"Orphaned nodes not present in edges: {missing}"
        return None

    def _canonicalize_edges(
        self, selected_nodes: list[str], edges: list[dict[str, str]]
    ) -> tuple[list[dict[str, str]], Optional[str]]:
        selected = list(selected_nodes)
        selected_set = set(selected)
        normalized_index: dict[str, str] = {}
        for node_id in selected:
            key = self._normalize_node_token(node_id)
            if key and key not in normalized_index:
                normalized_index[key] = node_id

        def resolve(endpoint: str) -> Optional[str]:
            token = str(endpoint or "").strip()
            if token in selected_set:
                return token
            norm = self._normalize_node_token(token)
            if norm in normalized_index:
                return normalized_index[norm]
            for node_id in selected:
                base = self._normalize_node_token(node_id)
                if base and norm.startswith(base):
                    return node_id
            return None

        out: list[dict[str, str]] = []
        for edge in edges:
            src_raw = str(edge.get("from", ""))
            dst_raw = str(edge.get("to", ""))
            src = resolve(src_raw)
            dst = resolve(dst_raw)
            if not src or not dst:
                return [], f"Edge contains unknown endpoint: {edge}"
            out.append({"from": src, "to": dst})
        return out, None

    def _normalize_node_token(self, token: str) -> str:
        v = re.sub(r"[^A-Za-z0-9]+", "_", (token or "").strip().upper()).strip("_")
        v = re.sub(r"_\d+$", "", v)
        return v

    def _materialize_artifact_paths(self, workflow: dict[str, Any]) -> dict[str, Any]:
        nodes = workflow.get("nodes", []) or []
        edges = workflow.get("edges", []) or []
        by_id = {n.get("id"): n for n in nodes if isinstance(n, dict) and n.get("id")}
        incoming: dict[str, list[str]] = {}
        for e in edges:
            src = e.get("from")
            dst = e.get("to")
            if not src or not dst:
                continue
            incoming.setdefault(dst, []).append(src)

        def ext_for(node_id: str) -> str:
            for src in incoming.get(node_id, []):
                up = by_id.get(src) or {}
                if up.get("type") != "CONVERT_TO_FILE":
                    continue
                cfg = up.get("config", {}) or {}
                op = str(cfg.get("operation", "")).lower()
                if op in {"csv", "ods", "xls", "xlsx"}:
                    return ".csv" if op == "csv" else f".{op}"
                if op == "tojson":
                    return ".json"
                if op == "totext":
                    return ".txt"
                if op == "html":
                    return ".html"
                if op == "tobinary":
                    return ".bin"
            return ".bin"

        workflow_id = str(workflow.get("workflow_id") or "workflow")
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("type") != "READ_WRITE_FILES_FROM_DISK":
                continue
            cfg = node.get("config", {}) or {}
            op = str(cfg.get("operation", "write")).lower()
            if op not in {"write", "writefile", "write_file"}:
                continue
            path = str(cfg.get("file_path_and_name", cfg.get("path", "")) or "")
            if path and "{{" not in path and "}}" not in path:
                continue
            node_id = str(node.get("id") or "node")
            cfg["file_path_and_name"] = f"/tmp/{workflow_id}_{node_id}{ext_for(node_id)}"
            node["config"] = cfg
        workflow["nodes"] = nodes
        return workflow

    def _inject_artifact_tail_if_needed(self, workflow: dict[str, Any], objective: str) -> dict[str, Any]:
        """Append deterministic file-output tail when objective implies artifacts."""
        if not self._objective_requires_file_outputs(objective):
            return workflow

        nodes = list(workflow.get("nodes", []) or [])
        edges = list(workflow.get("edges", []) or [])
        node_ids = [str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id")]
        if not node_ids:
            return workflow

        has_writer = any(
            isinstance(n, dict) and n.get("type") == "READ_WRITE_FILES_FROM_DISK"
            for n in nodes
        )
        if has_writer:
            return workflow

        max_idx = 0
        for nid in node_ids:
            m = re.fullmatch(r"n(\d+)", nid)
            if m:
                max_idx = max(max_idx, int(m.group(1)))

        convert_id = f"n{max_idx + 1:02d}"
        write_id = f"n{max_idx + 2:02d}"

        operation, ext = self._artifact_operation_and_extension(objective)
        file_name = self._safe_slug(str(workflow.get("workflow_id") or "workflow"))
        out_path = f"/tmp/{file_name}_artifact{ext}"

        convert_node = {
            "id": convert_id,
            "type": "CONVERT_TO_FILE",
            "label": "Convert Artifact",
            "config": {
                "operation": operation,
                "put_output_file_in_field": "data",
                "file_name": f"{file_name}_artifact",
            },
        }
        write_node = {
            "id": write_id,
            "type": "READ_WRITE_FILES_FROM_DISK",
            "label": "Write Artifact",
            "config": {
                "operation": "write",
                "file_path_and_name": out_path,
                "input_binary_field": "data",
            },
        }

        outgoing = {str(e.get("from")) for e in edges if isinstance(e, dict) and e.get("from")}
        terminals = [nid for nid in node_ids if nid not in outgoing]
        source_id = terminals[0] if terminals else node_ids[-1]

        edges.append({"from": source_id, "to": convert_id})
        edges.append({"from": convert_id, "to": write_id})
        nodes.extend([convert_node, write_node])
        workflow["nodes"] = nodes
        workflow["edges"] = edges
        return workflow

    def _objective_requires_file_outputs(self, objective: str) -> bool:
        text = objective.lower()
        keywords = [
            "artifact",
            "artifacts",
            "file",
            "files",
            "csv",
            "excel",
            "xlsx",
            "json",
            "markdown",
            "report",
            "output",
            "save to disk",
            "write",
        ]
        return any(k in text for k in keywords)

    def _artifact_operation_and_extension(self, objective: str) -> tuple[str, str]:
        text = objective.lower()
        if any(k in text for k in ("markdown", "md ")):
            return "toText", ".md"
        if any(k in text for k in ("json",)):
            return "toJson", ".json"
        if any(k in text for k in ("excel", "xlsx", "xls", "sheet", "table", "csv")):
            return "csv", ".csv"
        if any(k in text for k in ("html",)):
            return "html", ".html"
        return "toText", ".txt"

    def _safe_slug(self, value: str) -> str:
        s = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return s or "workflow"

    def _inject_trigger_if_missing(
        self, selected_nodes: list[str], edges: list[dict[str, str]]
    ) -> tuple[list[str], list[dict[str, str]]]:
        if any(n in _TRIGGER_TYPES for n in selected_nodes):
            return selected_nodes, edges
        if "MANUAL_TRIGGER" not in NODE_SPECS:
            return selected_nodes, edges
        selected = ["MANUAL_TRIGGER", *selected_nodes]
        inbound_targets = {e["to"] for e in edges}
        roots = [n for n in selected_nodes if n not in inbound_targets]
        target = roots[0] if roots else selected_nodes[0]
        new_edges = [{"from": "MANUAL_TRIGGER", "to": target}, *edges]
        return selected, new_edges

    def _validate_refs(
        self,
        inputs: dict[str, Any],
        *,
        node_id: str,
        upstream_outputs: dict[str, list[str]],
    ) -> Optional[str]:
        for _, value in (inputs or {}).items():
            if not isinstance(value, str):
                continue
            for match in _TEMPLATE_REF.finditer(value):
                src = match.group(1)
                out = match.group(2)
                if src == node_id:
                    return f"Forward/self reference detected in '{value}'."
                if src not in upstream_outputs:
                    return f"Reference source '{src}' is not upstream for node '{node_id}'."
                if out not in (upstream_outputs.get(src) or []):
                    return f"Reference output '{src}.{out}' does not exist in upstream outputs."
        return None

