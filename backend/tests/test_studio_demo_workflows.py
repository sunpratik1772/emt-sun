"""Studio demo workflows use approved nodes only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.copilot_validate import validate_dag_for_api
from engine.studio_nodes import STUDIO_APPROVED_NODE_TYPES

_GOOD_EXAMPLES = Path(__file__).resolve().parent.parent / "good_examples"


@pytest.mark.parametrize(
    "path",
    sorted(_GOOD_EXAMPLES.glob("studio_*.json")),
    ids=lambda p: p.name,
)
def test_studio_demo_uses_approved_nodes_only(path: Path) -> None:
    dag = json.loads(path.read_text())
    assert dag.get("tags") == ["studio_demo"]
    types = {n["type"] for n in dag["nodes"]}
    assert types <= STUDIO_APPROVED_NODE_TYPES, types - STUDIO_APPROVED_NODE_TYPES


def test_studio_demo_has_no_orphan_note_nodes() -> None:
    """Good examples must not include unwired note nodes (they disjoint the canvas)."""
    for path in sorted(_GOOD_EXAMPLES.glob("studio_*.json")):
        dag = json.loads(path.read_text())
        notes = [n["id"] for n in dag["nodes"] if n.get("type") == "note"]
        assert not notes, f"{path.name}: remove orphan note node(s) {notes}"


def test_studio_demo_rejects_legacy_node_type() -> None:
    dag = json.loads((_GOOD_EXAMPLES / "studio_04_product_360_join.json").read_text())
    dag["nodes"].append(
        {"id": "bad", "type": "FILTER", "config": {}, "position": {"x": 0, "y": 0}}
    )
    vr = validate_dag_for_api(dag)
    assert not vr.valid
    assert any(i.code == "UNKNOWN_TYPE" or "Studio" in i.message or "palette" in i.message for i in vr.errors)
