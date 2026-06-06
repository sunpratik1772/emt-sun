"""
Central node registry — built by *auto-discovering* `NODE_SPEC` from
``engine.nodes`` (Studio palette).

Design goal: adding a new Studio node is a **single-file** change under
``engine/nodes/``.

At import time we walk ``engine.nodes`` with ``pkgutil.iter_modules``,
import each submodule, and collect every module-level ``NODE_SPEC``.
Modules without a ``NODE_SPEC`` are skipped silently.

Everything downstream — ``engine.dag_runner``, ``engine.validator``,
``engine.jobs``, ``app.routers.copilot`` — consumes the lookup dicts
exposed here. None of them know about individual node modules.
"""
from __future__ import annotations

import importlib
import json
import hashlib
import pkgutil
from dataclasses import asdict, replace
from typing import Iterable

from . import nodes as _nodes_pkg
from .node_spec import Handler, NodeSpec, _spec
from .orchestrator_runtime import is_incoming_handler, wrap_incoming_handler
from .ports import ParamSpec, ParamType, PortSpec, PortType, Widget

from .node_availability import is_studio_active as _is_studio_active_node
from .node_availability import is_studio_placeholder as _is_studio_placeholder_node

_SECTION_NORMALIZATION: dict[str, dict[str, str | int]] = {
    # orchestrator-backend palette sections (https://github.com/sunpratik1772/orchestrator-backend)
    "triggers": {"id": "triggers", "label": "Triggers", "order": 5, "color": "#0EA5E9"},
    "data": {"id": "data", "label": "Data", "order": 10, "color": "#10B981"},
    "transform": {"id": "transform", "label": "Transform", "order": 15, "color": "#6366F1"},
    "logic": {"id": "logic", "label": "Logic", "order": 20, "color": "#F59E0B"},
    "integrations": {"id": "integrations", "label": "Integrations", "order": 25, "color": "#14B8A6"},
    "ai": {"id": "ai", "label": "AI", "order": 30, "color": "#8B5CF6"},
    "output": {"id": "output", "label": "Output", "order": 35, "color": "#EC4899"},
    # dbSherpa legacy aliases
    "control": {"id": "logic", "label": "Logic", "order": 20, "color": "#F59E0B"},
    "flow": {"id": "logic", "label": "Logic", "order": 20, "color": "#F59E0B"},
    "io": {"id": "integrations", "label": "Integrations", "order": 25, "color": "#14B8A6"},
    "integration": {"id": "integrations", "label": "Integrations", "order": 25, "color": "#14B8A6"},
}


def _is_studio_active(spec: NodeSpec) -> bool:
    """Studio exposes only active, non-legacy nodes to agent and prompt builder."""
    return _is_studio_active_node(spec)


def _is_studio_placeholder(spec: NodeSpec) -> bool:
    """Inactive nodes shown in the palette as coming-soon placeholders."""
    return _is_studio_placeholder_node(spec)


def _normalize_palette_fields(node_entry: dict) -> dict:
    """
    Normalize palette sections to short, de-duplicated Studio groups.

    We intentionally collapse:
      * control + flow -> flow
      * io + integration -> int
    """
    raw_sid = str(node_entry.get("palette_group", "")).strip().lower()
    normalized = _SECTION_NORMALIZATION.get(raw_sid)
    if normalized is None:
        # Keep unknown/custom buckets stable but short.
        sid = raw_sid or "misc"
        normalized = {
            "id": sid,
            "label": str(node_entry.get("palette_section_label", sid))[:12] or sid,
            "order": int(node_entry.get("palette_section_order", 99) or 99),
            "color": str(node_entry.get("palette_section_color", "#6B7280")),
        }
    return {
        **node_entry,
        "palette_group": str(normalized["id"]),
        "palette_section_label": str(normalized["label"]),
        "palette_section_order": int(normalized["order"]),
        "palette_section_color": str(normalized["color"]),
    }


def _collect_specs_from_package(
    pkg: object,
    found: dict[str, NodeSpec],
    *,
    package_label: str,
) -> None:
    """Import every submodule under *pkg* and merge NODE_SPEC / NODE_SPECS into *found*."""
    for module_info in pkgutil.iter_modules(pkg.__path__):  # type: ignore[attr-defined]
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{pkg.__name__}.{module_info.name}")  # type: ignore[attr-defined]
        specs: list[NodeSpec] = []
        spec = getattr(module, "NODE_SPEC", None)
        if isinstance(spec, NodeSpec):
            specs.append(spec)
        grouped_specs = getattr(module, "NODE_SPECS", ())
        if isinstance(grouped_specs, (list, tuple)):
            specs.extend(s for s in grouped_specs if isinstance(s, NodeSpec))
        for spec in specs:
            if is_incoming_handler(spec.handler):
                spec = replace(spec, handler=wrap_incoming_handler(spec.handler))
            if spec.type_id in found:
                raise RuntimeError(
                    f"Duplicate NODE_SPEC type_id '{spec.type_id}' — "
                    f"defined in both {package_label}/{module_info.name}.py and "
                    f"another node module."
                )
            found[spec.type_id] = spec


# -----------------------------------------------------------------------------
# Auto-discovery
# -----------------------------------------------------------------------------
def _discover_all_specs() -> tuple[NodeSpec, ...]:
    """Walk ``engine.nodes`` and collect every ``NODE_SPEC``."""
    found: dict[str, NodeSpec] = {}
    _collect_specs_from_package(
        _nodes_pkg,
        found,
        package_label="engine/nodes",
    )
    return tuple(sorted(found.values(), key=lambda s: s.type_id))


_SPECS_ALL: tuple[NodeSpec, ...] = _discover_all_specs()
_SPECS_STUDIO: tuple[NodeSpec, ...] = tuple(s for s in _SPECS_ALL if _is_studio_active(s))
_SPECS_PLACEHOLDER: tuple[NodeSpec, ...] = tuple(s for s in _SPECS_ALL if _is_studio_placeholder(s))


# -----------------------------------------------------------------------------
# Public lookups
# -----------------------------------------------------------------------------
NODE_SPECS: dict[str, NodeSpec] = {s.type_id: s for s in _SPECS_ALL}
NODE_HANDLERS: dict[str, Handler] = {s.type_id: s.handler for s in _SPECS_ALL}
"""Drop-in replacement for the old dag_runner map."""


def all_specs() -> Iterable[NodeSpec]:
    """Iterate Studio-active specs in palette order (sorted by type_id)."""
    return _SPECS_STUDIO


def placeholder_specs() -> Iterable[NodeSpec]:
    """Iterate UI-only placeholder specs (studio_active=false)."""
    return _SPECS_PLACEHOLDER


def get_spec(type_id: str) -> NodeSpec:
    try:
        return NODE_SPECS[type_id]
    except KeyError:
        raise ValueError(f"Unknown node type '{type_id}'") from None


def contracts_document(version: str = "1.0", *, studio_only: bool = False) -> dict:
    """
    Serialisable view of every live NodeSpec.

    Important naming note for maintainers:
    `NodeSpec` is the canonical node contract used by validation/runtime.
    This document is a derived JSON payload for Copilot, `/contracts`, and
    generated artifacts. If it looks wrong, fix the node YAML/handler and run
    `backend/scripts/gen_artifacts.py`; do not hand-edit
    `backend/contracts/node_contracts.json`.

    When ``studio_only`` is true, legacy/placeholder nodes are omitted — use
    this for Copilot generation prompts so retired types are not re-emitted.
    """
    specs = _SPECS_STUDIO if studio_only else _SPECS_ALL
    return {
        "version": version,
        "description": (
            "I/O contracts for dbSherpa node types. All datasets are pandas "
            "DataFrames passed by name through the shared RunContext."
        ),
        "nodes": {s.type_id: s.contract for s in specs},
    }


def ui_manifest() -> dict:
    """
    UI-facing manifest consumed by the frontend generator. Keeps the
    frontend free from any Python/backend coupling.
    """
    return {
        "version": 2,
        "nodes": [
            _normalize_palette_fields(
                {
                    "type_id": s.type_id,
                    "description": s.description,
                    **s.ui,
                    "input_ports": [p.to_json() for p in s.input_ports],
                    "output_ports": [p.to_json() for p in s.output_ports],
                    "params": [p.to_json() for p in s.params],
                }
            )
            for s in _SPECS_STUDIO
        ],
    }


def palette_sections_from_manifest_nodes(nodes: list[dict]) -> list[dict]:
    """
    Dedupe Studio palette rail sections from flattened per-node UI metadata
    (``palette_group`` / ``palette_section_*``). Used by ``gen_artifacts`` and
    :func:`studio_manifest`.
    """
    by_id: dict[str, dict[str, str | int]] = {}
    for n in nodes:
        sid = n.get("palette_group")
        if not sid:
            raise ValueError(
                f"palette_sections: node {n.get('type_id')!r} missing palette_group "
                f"(set ui.palette in NodeSpec YAML)"
            )
        sid = str(sid)
        label = str(n.get("palette_section_label", sid))
        color = str(n.get("palette_section_color", "#6B7280"))
        order = int(n.get("palette_section_order", 0))
        row = {"id": sid, "label": label, "order": order, "color": color}
        prev = by_id.get(sid)
        if prev is None:
            by_id[sid] = row
            continue
        if prev != row:
            raise ValueError(
                f"palette_sections: section {sid!r} has conflicting metadata "
                f"across nodes (e.g. {n.get('type_id')!r}); ui.palette.section "
                f"must match for every node in a section"
            )
    return list(by_id.values())


def _manifest_entry(spec: NodeSpec, *, include_contract: bool) -> dict:
    entry = {
        "type_id": spec.type_id,
        "description": spec.description,
        **spec.ui,
        "input_ports": [p.to_json() for p in spec.input_ports],
        "output_ports": [p.to_json() for p in spec.output_ports],
        "params": [p.to_json() for p in spec.params],
    }
    entry = _normalize_palette_fields(entry)
    if include_contract:
        c = spec.contract
        entry["contract"] = {
            "description": c.get("description", spec.description),
            "inputs": c.get("inputs") or {},
            "outputs": c.get("outputs") or {},
            "config_schema": c.get("config_schema") or {},
            "constraints": list(c.get("constraints") or []),
        }
    return entry


def studio_manifest() -> dict:
    """
    Single payload for the Studio UI.

    It includes:
      * palette sections and node UI metadata,
      * typed ports/params for config forms and validation display,
      * a small derived contract block for docs/help text.

    The payload is built from live :data:`NODE_SPECS`, so the frontend can
    refresh after backend changes without a rebuild.
    """
    um = ui_manifest()
    raw_nodes = um["nodes"]
    palette = palette_sections_from_manifest_nodes(raw_nodes)
    nodes_out = [_manifest_entry(NODE_SPECS[entry["type_id"]], include_contract=True) for entry in raw_nodes]

    placeholder_out = [
        _manifest_entry(spec, include_contract=False) for spec in _SPECS_PLACEHOLDER
    ]
    if placeholder_out:
        ph_palette = palette_sections_from_manifest_nodes(placeholder_out)
        by_id = {s["id"]: s for s in palette}
        for sec in ph_palette:
            by_id.setdefault(sec["id"], sec)
        palette = list(by_id.values())

    # Lightweight revision token for UI auto-refresh. Any shape/ordering/config
    # change in node palette metadata, ports, params, or contracts updates this.
    revision_payload = {
        "version": um["version"],
        "palette_sections": sorted(palette, key=lambda x: int(x["order"])),
        "nodes": nodes_out,
        "placeholder_nodes": placeholder_out,
    }
    manifest_revision = hashlib.sha1(
        json.dumps(revision_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "version": um["version"],
        "manifest_revision": manifest_revision,
        **revision_payload,
    }


# Re-export the primitives so node modules that want to stay within
# the `engine.registry` namespace still can. The canonical import path
# for new code is `engine.node_spec` / `engine.ports`.
__all__ = [
    "NodeSpec",
    "Handler",
    "_spec",
    "ParamSpec",
    "ParamType",
    "PortSpec",
    "PortType",
    "Widget",
    "NODE_SPECS",
    "NODE_HANDLERS",
    "all_specs",
    "placeholder_specs",
    "get_spec",
    "contracts_document",
    "ui_manifest",
    "palette_sections_from_manifest_nodes",
    "studio_manifest",
    "asdict",  # re-export for scripts that dump specs
]
