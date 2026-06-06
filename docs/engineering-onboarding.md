# Engineering Onboarding Guide

> For engineers joining the team. Walks through the codebase, gets you productive
> on day one, and explains how everything fits together.
>
> **Last updated:** May 2026 — backend packages `connectors/`, `generation/`, `integrations/mcp/`; vetted demos in `good_examples/`; 36-node palette.

---

## Backend restructure (May 2026)

Legacy paths **`backend/agent/`** and **`backend/data_sources/`** are removed. Use these instead:

| Old (removed) | New (canonical) |
|---------------|-----------------|
| `data_sources/metadata/` | `connectors/metadata/` |
| `from data_sources import …` | `from connectors import get_registry, get_rows` |
| `agent/harness/runner.py` | `generation/harness/runner.py` |
| `agent/generation_guardrails.md` | `generation/generation_guardrails.md` |
| `backend/workflows/studio_*.json` | `backend/good_examples/studio_*.json` |

Import MCP live tools from `integrations.mcp`, not `mcp_bridge` (HTTP demo server only).

---

## What is dbSherpa Studio?

**dbSherpa Studio** is a **visual workflow automation platform**:

1. **Drag nodes** onto a canvas (data sources, transforms, AI agents, integrations).
2. **Wire edges** to form a directed acyclic graph (DAG).
3. **Click Run** — the backend executes nodes in topological order with live SSE updates.
4. **Use sherpa (Copilot)** — describe a pipeline in English; the **generation harness**
   (`backend/generation/`) generates, validates, auto-fixes, and smoke-tests a workflow
   before loading it on the canvas.

Primary users: data engineers, surveillance analysts, and ops teams building pipelines
without shipping full applications.

---

## Your first 30 minutes

### 1. Clone and run

```bash
git clone https://github.com/sunpratik1772/sherpa-latest.git
cd sherpa-latest
echo 'GEMINI_API_KEY=your_key' > backend/.env
./start.sh
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8001/api/health |
| MCP bridge | http://localhost:8765/health (auto-started) |

Logs: `.run/logs/backend.log`, `.run/logs/frontend.log`

### 2. Log in

Open http://localhost:3000 → **Login as Demo User** (local dev account).

Production auth supports email/password and Google OAuth (`backend/app/routers/auth.py`).

### 3. Understand the layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Topbar   [env] / [workflow name]  [validate] [run] [theme]      │
├────────┬─────────────────────────────┬───────────┬───────────────┤
│ Left   │  NodePanel │ WorkflowCanvas │ Activity  │  Right Panel  │
│ Nav    │  (palette) │  (ReactFlow)   │  Rail     │  Config /     │
│        │            │                │           │  Run Log /    │
│        │            │                │           │  sherpa       │
├────────┴─────────────────────────────┴───────────┴───────────────┤
│  Bottom Output Panel  (when Output mode — stacked stage cards)     │
└──────────────────────────────────────────────────────────────────┘
```

**Activity rail** (right edge icons): Config · Run Logs · sherpa · Output

When **Output** is active, the bottom panel shows each finished node as an expandable
card stacked vertically, then **Final Output** (disposition, downloads).

### 4. Load and run a demo

- Left nav → **Workflow** drawer
- Open `studio_10_leads_tier_mcp_publish.json` (or any `studio_*.json`)
- Click **Run** (play icon in canvas toolbar or topbar)
- Open **Output** on the activity rail — see per-stage results stacked top-to-bottom

### 5. Try sherpa (Copilot)

- Activity rail → **sherpa**
- Mode: **Build** (generate) vs **Ask** (chat)
- Example prompt: *"Monitor market_ticks for spread_pips > 100 and post to Confluence"*
- Watch SSE timeline: analyzing → planning → creating nodes → smoke test → design summary
- Generated workflow loads on canvas; use undo checkpoint on the message bubble to revert

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Tailwind, Zustand, ReactFlow |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pandas |
| User code | Starlark sandbox (`code` node) |
| LLM | Google Gemini (`google-genai`) |
| Integrations | MCP HTTP bridge (Confluence, Jira, GitHub) |
| Persistence | SQLite default; optional MySQL |
| Deploy | Docker, Cloud Run (GCP) |

---

## Repo layout

```
sheep-latest/
├── frontend/src/
│   ├── components/       Canvas, Copilot, RightPanel, BottomOutputPanel, Topbar
│   ├── store/            workflowStore (central), nodeRegistryStore, authStore
│   ├── services/api.ts   All HTTP + SSE calls
│   └── nodes/generated.ts   AUTO-GENERATED palette metadata
│
├── backend/
│   ├── app/              FastAPI routers, database, scheduler
│   ├── engine/           DAG runner, validator, nodes/*.yaml + *.py
│   ├── generation/       AgentRunner, planner, repair, prompt_builder
│   ├── connectors/       Dataset metadata YAML + connector registry
│   ├── integrations/mcp/ Live GitHub, Jira, Confluence tools
│   ├── copilot/          WorkflowCopilot, SSE adapter, run analyst
│   ├── mcp_bridge/       Integration HTTP server (:8765)
│   ├── skills/           Domain skill markdown for Copilot prompts
│   ├── good_examples/    studio_*.json vetted demos (15 workflows)
│   └── scripts/          gen_artifacts.py, harness benchmarks, reset_db.py
│
├── docs/                 This documentation set
└── start.sh              Start backend :8001 + frontend :3000
```

**Legacy removed:** `backend/engine/nodes_legacy/` — do not reference n8n-era type IDs.

---

## Core concepts

### Workflows

JSON document with `nodes` and `edges`:

```json
{
  "name": "Lead Scoring Pipeline",
  "nodes": [
    { "id": "n01", "type": "csv_extract", "label": "Load Leads", "config": { "source": "leads.csv" } },
    { "id": "n02", "type": "filter", "label": "Hot Leads", "config": { "expression": "row.score >= 80" } },
    { "id": "n03", "type": "excel_output", "label": "Export", "config": { "filename": "hot_leads.xlsx" } }
  ],
  "edges": [
    { "from": "n01", "to": "n02" },
    { "from": "n02", "to": "n03" }
  ]
}
```

Edges use `from` / `to` (not ReactFlow's source/target in persisted JSON).

### Nodes (36 active)

Each node = **YAML spec** + **Python handler**:

| File | Role |
|------|------|
| `backend/engine/nodes/<type>.yaml` | Metadata: ports, params, UI, palette section |
| `backend/engine/nodes/<type>.py` | `run()` handler + `NODE_SPEC = _spec_from_yaml(...)` |

Registry auto-discovers at import — no manual registration.

Palette sections: Triggers · Data · Transform · Logic · AI · Integrations · Output

See [Node Catalogue](./node-catalogue.md).

### RunContext

Shared state during execution:

```python
ctx.datasets["n02_output"]   # DataFrame or row dict from upstream
ctx.values["total"]            # Scalars from function nodes
ctx.set("flag", True)          # Generic key-value
```

Handlers receive `incoming: dict[str, Any]` mapping upstream node IDs to outputs.

### sherpa (Copilot)

Natural language → validated workflow via **AgentRunner**:

```
Prompt → Understanding → Planning (skills + schemas)
      → [optional parallel pre-tasks]
      → Generating (Gemini) → Canonicalize → Validate
      → AutoFix (deterministic) → LLM repair loop
      → Runtime smoke test → Final workflow + design summary
```

See [Sherpa Agent Harness](./generation-harness.md).

### Automations

Scheduled or interval runs of saved workflows:

- API: `backend/app/routers/automations.py`
- Scheduler: `backend/app/scheduler.py` (polls every 10s)
- UI: Left nav → **Automations**

---

## How things connect

### Frontend → Backend

`frontend/src/services/api.ts` — Vite proxies `/api/*` → `localhost:8001`.

| Endpoint | Use |
|----------|-----|
| `POST /api/run/stream` | Execute workflow (SSE) |
| `POST /api/validate` | Pre-flight validation |
| `POST /api/copilot/generate/stream` | Sherpa build mode (SSE) |
| `POST /api/copilot/explain-run/stream` | Post-run analysis |
| `GET /api/node-manifest` | Palette metadata |
| `GET/POST /api/automations` | Scheduled runs |

### Run flow (UI)

```
Run click → api.runWorkflowStream()
         → workflowStore.applyRunEvent() (queued SSE processing)
         → Canvas animates nodes; Output panel stacks stage cards
         → workflow_complete → Final Output section
```

### Generate flow (UI)

```
Prompt → copilotGenerateStream()
      → workflow_created event → setWorkflow() + auto-layout
      → text chunks → markdown assistant message
      → User clicks Run separately (auto-run after generate is disabled)
```

---

## Common development tasks

### Add a node

[Creating Nodes](./creating-nodes.md) — YAML + PY + `gen_artifacts.py`

### Add a data source

[Data Source Onboarding](./data-source-onboarding.md) — YAML in `connectors/metadata/` + connector kind

### Modify UI

| Area | File |
|------|------|
| Node config forms | `RightPanel/ConfigView.tsx` |
| Canvas | `WorkflowCanvas/` |
| Run output | `RightPanel/OutputView.tsx`, `BottomOutputPanel.tsx` |
| Copilot | `Copilot/index.tsx` |
| Global state | `store/workflowStore.ts` |

### Run tests

```bash
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_studio_demo_workflows.py -q
python -m pytest tests/test_parallel_runner_integration.py -q
```

### Reset local database

```bash
python backend/scripts/reset_db.py
```

Re-creates SQLite tables. User workloads in DB are cleared; `good_examples/` on disk is preserved.

### Benchmark Copilot prompts

```bash
GEMINI_API_KEY=... python backend/scripts/run_harness_prompt_matrix.py --all
```

Results: `backend/scripts/harness_prompt_matrix_summary.md`

---

## Key files

| File | Why read it |
|------|-------------|
| `backend/engine/dag_runner.py` | Workflow execution |
| `backend/engine/registry.py` | Node discovery |
| `backend/generation/harness/runner.py` | Copilot control loop |
| `backend/connectors/registry.py` | Dataset registry + `get_rows()` |
| `backend/good_examples/studio_*.json` | Vetted demo workflows for e2e + few-shot |
| `frontend/src/store/workflowStore.ts` | Frontend state + SSE run queue |
| `frontend/src/services/api.ts` | All API calls |
| `backend/app/database.py` | Persistence layer |

---

## Environment variables

### Required

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Agent nodes + Copilot |

### Common optional

| Variable | Purpose |
|----------|---------|
| `MCP_BRIDGE_MODE=demo` | Mock MCP (default — no tokens needed) |
| `ATLASSIAN_*`, `GITHUB_*` | Live Confluence/Jira/GitHub |
| `TEAMS_INCOMING_WEBHOOK_URL` | Microsoft Teams node |
| `DATABASE_URL` or `MYSQL_*` | MySQL instead of SQLite |

Full reference: [docs/README.md](./README.md#environment-variables)

---

## Conventions

- **Python:** `snake_case`, type hints
- **TypeScript:** strict mode, functional components
- **Node IDs in workflows:** `n01`, `n02`, …
- **Never hand-edit:** `node_contracts.json`, `generated.ts`, `node_type_ids.py`, `node_detail.md`
- **Starlark:** no imports; use `output = [...]` or comprehensions

---

## Further reading

| Doc | Topic |
|-----|-------|
| [Node Catalogue](./node-catalogue.md) | Every node |
| [Creating Nodes](./creating-nodes.md) | Build a node |
| [Data Source Onboarding](./data-source-onboarding.md) | Add datasets |
| [Sherpa Agent Harness](./generation-harness.md) | Routing, clarification, harness, UI stream |
| [MCP Integrations](./mcp-integrations.md) | GitHub/Jira/Confluence creds, bridge tools, Teams/Outlook |
| [Architecture](./architecture.md) | Diagrams + deployment |
| [Database](./database.md) | Schema + MySQL setup |
