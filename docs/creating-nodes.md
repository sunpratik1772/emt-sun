# Creating a New Node

> Step-by-step guide to adding a new node to the Studio palette.
> A new node is a **two-file** change (`<type_id>.yaml` + `<type_id>.py`)
> plus a regeneration of build artifacts.
>
> **May 2026:** Node handlers live in `engine/nodes/`; dataset schemas in `connectors/metadata/`; vetted demos in `good_examples/`.

---

## Backend restructure (May 2026)

| Topic | Location |
|-------|----------|
| Node YAML + handler | `backend/engine/nodes/<type_id>.yaml` + `.py` |
| Dataset ids for config dropdowns | `backend/connectors/metadata/*.yaml` |
| Demo workflow for e2e | `backend/good_examples/studio_XX_….json` |
| Regenerate palette artifacts | `python backend/scripts/gen_artifacts.py` |

Do **not** add nodes under legacy paths or register datasets in removed `data_sources/`.

---

## Overview

```
backend/engine/nodes/
  my_node.yaml    <-- 1. Metadata: name, ports, params, UI hints
  my_node.py      <-- 2. Handler: runtime logic

$ python backend/scripts/gen_artifacts.py   <-- 3. Regenerate artifacts
```

The YAML is the **single source of truth** for all node metadata. The Python
file contains only runtime logic and a one-liner that wires the two together.

---

## Step 1: Create the YAML spec

**File:** `backend/engine/nodes/<type_id>.yaml`

### Full annotated template

```yaml
# ── Identity ──────────────────────────────────────────────────────────
type_id: my_node                          # Unique snake_case identifier
description: >-                           # One-liner for palette tooltip
  Does something useful with the incoming data rows.

# ── UI metadata ───────────────────────────────────────────────────────
ui:
  display_name: My Node                   # Short name on the canvas card
  icon: Sparkles                          # Lucide icon name (see below)
  color: "#8b5cf6"                        # Hex color for the card header
  palette:
    section:
      id: transform                       # Palette rail section (required)
      # label, color, order are inherited from the section defaults

# ── Ports ─────────────────────────────────────────────────────────────
input_ports:
  - name: rows                            # Port name (used in edge wiring)
    type: dataframe                       # dataframe | text | object | scalar | any
    optional: false                       # true = node can run without this input
    description: Table rows from upstream.

output_ports:
  - name: rows
    type: dataframe
    description: Transformed rows.
    # store_at: datasets.my_output        # Optional: explicit ctx storage path

# ── Parameters ────────────────────────────────────────────────────────
params:
  # --- Simple text field ---
  - name: label
    type: string
    required: false
    default: "default_value"
    widget: text                          # or textarea
    placeholder: "Enter a label"
    description: Human-readable label.

  # --- Number field ---
  - name: threshold
    type: number                          # also: integer
    required: true
    default: 0.5
    widget: number
    description: Score cutoff.

  # --- Boolean toggle ---
  - name: verbose
    type: boolean
    required: false
    default: false
    widget: switch                        # or checkbox
    description: Enable verbose output.

  # --- Dropdown select ---
  - name: mode
    type: enum
    required: true
    default: strict
    enum: [strict, lenient, auto]
    widget: select

  # --- JSON object ---
  - name: options
    type: json
    required: false
    widget: json
    description: Advanced configuration as JSON.

  # --- Code editor ---
  - name: script
    type: code
    required: true
    widget: starlark                      # starlark | code (Python)
    placeholder: "output = [r for r in rows if r.get('active')]"

  # --- Expression editor ---
  - name: expression
    type: expression
    required: true
    widget: code
    placeholder: "row.score >= 75"

  # --- Password / secret ---
  - name: api_token
    type: string
    required: false
    widget: password
    description: API token (masked in UI).

  # --- Conditional visibility ---
  - name: advanced_limit
    type: number
    required: false
    default: 100
    visible_if: { mode: strict }          # Only shown when mode=strict
    description: Row limit in strict mode.

  # --- Visible if value in list ---
  - name: format
    type: string
    required: false
    visible_if: { mode: [strict, auto] }  # Shown for strict OR auto

# ── Constraints (optional) ────────────────────────────────────────────
constraints:
  - Do not pass null values in the threshold field.
  - Maximum 1000 rows recommended for perRow mode.

# ── Semantics (optional) ─────────────────────────────────────────────
semantics:
  requires: [trader, time]                # Upstream data must have these semantic tags
```

### Palette section IDs

Use one of these built-in sections. All nodes in a section share its label,
color, and sort order in the sidebar rail.

| Section ID | Label | Color | Order | Typical nodes |
|------------|-------|-------|-------|---------------|
| `triggers` | Triggers | `#0EA5E9` | 5 | manual_trigger, schedule, api_trigger |
| `data` | Data | `#10B981` | 10 | csv_extract, db_query, http |
| `transform` | Transform | `#6366F1` | 15 | filter, sort, group_by, join |
| `logic` | Logic | `#F59E0B` | 20 | code, condition, router, function |
| `ai` | AI | `#8B5CF6` | 30 | agent, evaluator |
| `integrations` | Integrations | `#14B8A6` | 25 | mcp, github, slack, teams, outlook, gmail |
| `output` | Output | `#EC4899` | 35 | excel_output, response, note |

### Lucide icons

The Studio uses [Lucide](https://lucide.dev/icons) icons. Common choices:

| Icon | Good for |
|------|----------|
| `Bot` | AI/agent nodes |
| `Code2` | Code/script nodes |
| `Database` | Database sources |
| `Table2` | Tabular data |
| `Filter` | Filtering |
| `GitBranch` | Branching/conditions |
| `Merge` | Joining/combining |
| `Globe` | HTTP/web |
| `FileSpreadsheet` | Excel/spreadsheet |
| `Download` | Export/output |
| `Mail` | Email |
| `MessageSquare` | Chat/messaging |
| `Cpu` | Integration/processing |
| `Sparkles` | AI-enhanced features |
| `Wand2` | Transformation |
| `BarChart3` | Aggregation/charts |
| `Play` | Triggers/start |
| `Clock` | Scheduling |

---

## Step 2: Create the handler

**File:** `backend/engine/nodes/<type_id>.py`

### Handler with upstream data (3-param signature)

Most nodes that transform or process data use this pattern:

```python
"""Short description of what this node does."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent
logger = logging.getLogger(__name__)


def _upstream_rows(incoming: dict[str, Any]) -> list[dict]:
    """Extract rows from the first upstream node that has them."""
    for out in incoming.values():
        if isinstance(out, dict) and isinstance(out.get("rows"), list):
            return list(out["rows"])
    return []


def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    rows = _upstream_rows(incoming)

    threshold = float(cfg.get("threshold", 0.5))
    mode = cfg.get("mode", "strict")

    # ── Your logic here ──
    if mode == "strict":
        result = [r for r in rows if (r.get("score") or 0) >= threshold]
    else:
        result = rows

    return {
        "rows": result,
        "rowCount": len(result),
    }


# Wire YAML + handler together. Must be at module level.
NODE_SPEC = _spec_from_yaml(_HERE / "my_node.yaml", run)
```

### Handler without upstream data (2-param signature — triggers/sources)

```python
"""Source node that produces data without upstream input."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..context import RunContext
from ..node_spec import _spec_from_yaml

_HERE = Path(__file__).parent


def run(node: dict, ctx: RunContext) -> dict[str, Any]:
    cfg = node.get("config") or {}

    # Produce data from an external source
    rows = [
        {"id": 1, "name": "Alice", "score": 90},
        {"id": 2, "name": "Bob", "score": 75},
    ]

    return {
        "rows": rows,
        "rowCount": len(rows),
    }


NODE_SPEC = _spec_from_yaml(_HERE / "my_source.yaml", run)
```

### Multi-input handler (like Join)

```python
def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}

    # Iterate ALL upstream outputs (order follows edge list in workflow JSON)
    all_rows = []
    for upstream_id, output in incoming.items():
        if isinstance(output, dict) and isinstance(output.get("rows"), list):
            all_rows.append(output["rows"])

    left = all_rows[0] if len(all_rows) > 0 else []
    right = all_rows[1] if len(all_rows) > 1 else []

    # ... join logic ...
```

---

## How the handler is detected and wrapped

The **registry** (`backend/engine/registry.py`) auto-discovers your node:

1. At import time, it walks `backend/engine/nodes/`.
2. It imports your module and finds the `NODE_SPEC` variable.
3. It inspects your handler's signature:
   - **2 params** (`node, ctx`) -> called directly.
   - **3 params** with the third named `incoming` -> automatically wrapped by
     `orchestrator_runtime.py` to inject upstream outputs.
4. The handler is registered in `NODE_HANDLERS[type_id]`.

You don't need to edit `registry.py`, `dag_runner.py`, or any other file.

---

## Step 3: Regenerate artifacts

```bash
python backend/scripts/gen_artifacts.py
```

This produces four files:

| File | Purpose |
|------|---------|
| `backend/engine/node_type_ids.py` | `NodeType` Python enum |
| `backend/contracts/node_contracts.json` | Copilot + API JSON contracts |
| `frontend/src/nodes/generated.ts` | UI types, colors, icons, palette |
| `node_detail.md` | Human-readable node catalogue |

---

## Step 4: Test

### Quick smoke test

```python
# backend/tests/test_my_node.py
from engine.registry import NODE_SPECS

def test_my_node_registered():
    assert "my_node" in NODE_SPECS

def test_my_node_handler():
    spec = NODE_SPECS["my_node"]
    # Build a minimal node dict
    node = {"id": "n01", "type": "my_node", "config": {"threshold": 0.5}}
    # ... call handler with mock data ...
```

### Integration test with a workflow

```python
from engine.dag_runner import run_workflow

workflow = {
    "name": "test_my_node",
    "nodes": [
        {"id": "n01", "type": "manual_trigger", "config": {}},
        {"id": "n02", "type": "my_node", "config": {"threshold": 0.8}},
    ],
    "edges": [{"source": "n01", "target": "n02"}],
}
result = run_workflow(workflow)
```

---

## Step 5: Commit

```bash
git add backend/engine/nodes/my_node.yaml \
        backend/engine/nodes/my_node.py \
        backend/engine/node_type_ids.py \
        backend/contracts/node_contracts.json \
        frontend/src/nodes/generated.ts \
        node_detail.md

git commit -m "Add my_node to Studio palette"
```

---

## Step 6 (optional): Add a demo workflow

Create a workflow JSON under `backend/good_examples/` (for vetted demos) or save via the Studio UI / `POST /api/workflows/{filename}`:

```json
{
  "name": "My Node Demo",
  "nodes": [
    {"id": "n01", "type": "csv_extract", "config": {"source": "leads.csv"}},
    {"id": "n02", "type": "my_node", "config": {"threshold": 80}},
    {"id": "n03", "type": "response", "config": {}}
  ],
  "edges": [
    {"from": "n01", "to": "n02"},
    {"from": "n02", "to": "n03"}
  ]
}
```

For a vetted Studio demo, add `studio_XX_my_node_demo.json` under `good_examples/` and ensure `tests/test_studio_workflows_e2e.py` can execute it.

---

## Runtime flow diagram

```
   Workflow JSON
        │
        v
  ┌──────────────┐
  │  DAG Runner   │  dag_runner.py
  │  (topo sort)  │
  └──────────────┘
        │
        │  for each node in order:
        v
  ┌──────────────┐
  │  Registry     │  registry.py
  │  lookup       │  NODE_HANDLERS[type_id]
  └──────────────┘
        │
        v
  ┌──────────────────────┐
  │  Orchestrator        │  orchestrator_runtime.py
  │  Runtime             │
  │                      │
  │  build_incoming_     │ ─── builds {upstream_id: output} dict
  │  outputs()           │
  │                      │
  │  handler(node, ctx,  │ ─── calls YOUR handler
  │          incoming)   │
  │                      │
  │  apply_output_       │ ─── merges output into RunContext
  │  to_ctx()            │     (datasets, values, report_path)
  └──────────────────────┘
        │
        v
  ┌──────────────┐
  │  Port type    │  dag_runner.py
  │  checking     │  validates output matches declared ports
  └──────────────┘
        │
        v
  ┌──────────────┐
  │  Next node    │
  └──────────────┘
```

---

## Common patterns

### Access the run context directly

```python
def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    # Read a dataset stored by an earlier node
    df = ctx.datasets.get("leads_output")

    # Read a scalar value
    count = ctx.values.get("total_count", 0)

    # Store something for later nodes
    ctx.set("my_flag", True)
```

### Async handlers

If your handler needs to call an async API:

```python
import asyncio

def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    async def _fetch():
        # ... async logic ...
        return result

    result = asyncio.get_event_loop().run_until_complete(_fetch())
    return {"rows": result, "rowCount": len(result)}
```

### Error handling

```python
def run(node: dict, ctx: RunContext, incoming: dict[str, Any]) -> dict[str, Any]:
    cfg = node.get("config") or {}
    if not cfg.get("required_field"):
        raise ValueError("required_field is missing from node config")

    try:
        result = risky_operation()
    except SomeError as exc:
        raise RuntimeError(f"My node failed: {exc}") from exc

    return {"rows": result, "rowCount": len(result)}
```

### Hiding a node from the palette (legacy/deprecated)

Add `config_tags` to the YAML:

```yaml
ui:
  display_name: Old Node
  icon: Box
  color: "#6B7280"
  config_tags: [legacy]       # Hidden from Studio palette, still works at runtime
  palette:
    section: { id: transform }
```

---

## Checklist

- [ ] Created `backend/engine/nodes/<type_id>.yaml` with type_id, description, ui, ports, params
- [ ] Created `backend/engine/nodes/<type_id>.py` with `run()` and `NODE_SPEC = _spec_from_yaml(...)`
- [ ] Handler signature matches: 2-param for sources, 3-param (with `incoming`) for transforms
- [ ] Return dict includes `rows` + `rowCount` for dataframe outputs
- [ ] Ran `python backend/scripts/gen_artifacts.py` successfully
- [ ] Node appears in `node_detail.md`
- [ ] Node appears in `frontend/src/nodes/generated.ts`
- [ ] Added test under `backend/tests/`
- [ ] (Optional) Added demo workflow under `backend/good_examples/` and covered by e2e test
