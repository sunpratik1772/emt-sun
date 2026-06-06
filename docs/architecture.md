# Architecture

> How dbSherpa Studio is built — frontend to backend, request to response.
> **May 2026:** Copilot lives in `generation/`; datasets in `connectors/`; demos in `good_examples/`.

---

## Backend restructure (May 2026)

| Package | Responsibility |
|---------|----------------|
| `connectors/` | Dataset catalog (`metadata/*.yaml`), `get_rows()`, SQLite/Solr/Oracle/CSV backends |
| `generation/` | Copilot harness — `AgentRunner`, planner, repair, guardrails |
| `integrations/mcp/` | Live GitHub, Jira, Confluence tool implementations |
| `engine/` | DAG runner, validator, `nodes/*.yaml` + `*.py` handlers |
| `copilot/` | Sherpa routing, clarification, follow-ups, SSE adapters (calls `generation/`) — see [Sherpa Agent Harness](./generation-harness.md) |
| `mcp_bridge/` | HTTP MCP server on `:8765` (demo + live tools) — [MCP Integrations](./mcp-integrations.md) |
| `good_examples/` | 15 vetted `studio_*.json` demos (few-shot + e2e tests) |

User-saved workflows live in the **DB** (`workflows` table), not on disk under `backend/workflows/`.

---

## System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (Studio UI)                        │
│                                                                     │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Workflow  │ │   Right      │ │ Copilot  │ │  Bottom Output    │  │
│  │ Canvas   │ │   Panel      │ │ Panel    │ │  Panel            │  │
│  │(ReactFlow)│ │(Config/Logs) │ │(SSE chat)│ │(run results)     │  │
│  └────┬─────┘ └──────┬───────┘ └────┬─────┘ └───────┬───────────┘  │
│       │              │              │               │              │
│       └──────────────┴──────────────┴───────────────┘              │
│                              │                                      │
│                    Zustand Store (workflowStore)                     │
│                              │                                      │
│                    Services (api.ts)                                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  HTTP / SSE
                               │  /api/*
                               v
┌──────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (:8001)                        │
│                                                                      │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌────────────┐  │
│  │ /run    │ │/validate │ │/copilot │ │/workflows│ │/node-      │  │
│  │ /run/   │ │          │ │/generate│ │ /drafts  │ │ manifest   │  │
│  │ stream  │ │          │ │/stream  │ │          │ │            │  │
│  └────┬────┘ └────┬─────┘ └────┬────┘ └────┬─────┘ └─────┬──────┘  │
│       │           │            │           │             │          │
│       v           v            v           │             │          │
│  ┌─────────────────────┐  ┌────────────────┐   │       ┌─────v──────┐  │
│  │    DAG Runner       │  │  Generation    │   │       │  Registry  │  │
│  │  (topo sort +       │  │  Harness       │   │       │ (NodeSpec  │  │
│  │   execute)          │  │  generation/   │   │       │  auto-     │  │
│  │                     │  │  runner,       │   │       │  discover) │  │
│  │  ┌───────────────┐  │  │  planner,      │   │       └────────────┘  │
│  │  │ Node Handlers │  │  │  repair)       │   │                      │
│  │  │ (nodes/*.py)  │  │  └─────┬──────────┘   │                      │
│  │  └───────────────┘  │        │           │                      │
│  └──────────┬──────────┘        v           │                      │
│             │             ┌────────────┐    │                      │
│             v             │ Gemini LLM │    │                      │
│  ┌──────────────────┐     └────────────┘    │                      │
│  │  MCP Bridge      │  ┌────────────────────┘                      │
│  │  (:8765)         │  │                                           │
│  │  Confluence/     │  │  ┌────────────────────┐                   │
│  │  Jira/GitHub     │  └──│ good_examples/     │                   │
│  └──────────────────┘     │ studio_*.json      │                   │
│                           └────────────────────┘                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Frontend

**Stack:** React 18 + TypeScript + Vite + Tailwind CSS + Zustand + TanStack Query + ReactFlow

> **Detailed reference:** [Frontend Architecture](./frontend-architecture.md) — module map, global patterns, data flows, conventions, and known debt.

### Studio layout

```
┌──────────────────────────────────────────────────────────────────┐
│ LeftNav │ Topbar                                                 │
│         ├────────────────────────────────────────────────────────┤
│         │ NodePanel │ WorkflowCanvas / CodeEditor │ Activity │ RightPanel │
│         ├────────────────────────────────────────────────────────┤
│         │ BottomOutputPanel (run output — human-readable + JSON) │
└──────────────────────────────────────────────────────────────────┘
```

Entry: `main.tsx` (router + QueryClient) → `App.tsx` (studio shell). Routes: `/login`, `/docs`, `/dashboard` (protected).

### Key directories

```
frontend/src/
  main.tsx, App.tsx         Bootstrap + studio shell
  components/
    WorkflowCanvas/         React Flow editor (lazy-loaded)
    WorkflowCodeEditor/     Monaco editor (lazy-loaded)
    WorkflowDrawer/         Saved workflows + drafts
    RightPanel/             ConfigView, run log, output, copilot host
    Copilot/                LLM chat (lazy-loaded, SSE streaming)
    drawers/                Library drawers (Skills, Data, Runs, Nodes, Automations)
    NodePanel/              Palette + ⌘K search
    Topbar/                 Run, save, validate, import/export
    ToastHost.tsx           Global notifications
    Modal.tsx               Focus-trapped dialogs
  hooks/
    useLibraryQueries.ts    TanStack Query for library/automation API
    queryKeys.ts            Shared cache keys
  store/
    workflowStore.ts        Composes workflow slices (see below)
    workflow/               workflowSlice, runStream, copilotSlice, uiSlice
    authStore.ts            Cookie session + demo auth
    toastStore.ts           Global toast queue
    nodeRegistryStore.ts    Live node manifest
    studioSectionStore.ts   Left-nav drawer routing
  services/api.ts           HTTP + SSE client
  nodes/generated.ts        AUTO-GENERATED node manifest
```

### State management

**Composed Zustand store** (`workflowStore.ts`) — logic lives in slice modules under `store/workflow/`:

| Slice | Module | What it holds |
|-------|--------|---------------|
| Workflow | `workflowSlice.ts` | DAG editing, undo history, selection |
| Run | `runStream.ts` | SSE stream, per-node status, run results, validation issues |
| Copilot | `copilotSlice.ts` | Chat messages, generation timeline, undo checkpoints |
| UI | `uiSlice.ts` | Right panel mode, pane sizes, workspace view, mobile palette |

**Separate stores:** `authStore`, `themeStore`, `toastStore`, `nodeRegistryStore`, `studioSectionStore`.

**TanStack Query** caches read-mostly library data (skills, data sources, run logs, workflows, drafts, automations, copilot chats). Drawers fetch with `enabled: open`.

### Data flow: user clicks Run

```
User clicks Run (SaveBeforeRunDialog if dirty)
    → api.runWorkflowStream(workflow) → SSE
    → runStream slice processes events:
        node_start / node_complete / node_error / workflow_complete
    → setRightPanelMode('output') → BottomOutputPanel
    → HumanReadableOutput + collapsible raw JSON
```

### Data flow: Copilot generates a workflow

```
User prompt in Copilot
    → api stream (copilot generate) → SSE timeline phases
    → On complete: workflowStore.setWorkflow(generated)
    → Canvas renders new DAG
```

### Cross-cutting

| Concern | Location |
|---------|----------|
| Auth | `authStore` + `ProtectedRoute` |
| Toasts | `toastStore` + `ToastHost` |
| Errors | Regional `ErrorBoundary` in App + app-level in main |
| Lazy chunks | Canvas, Monaco, Copilot, DocsPage |
| Tests | Vitest (utils), Playwright (E2E smoke) |

### Build

```bash
cd frontend
npm run dev          # Vite dev server (:3000), proxies /api → :8001
npm run build        # tsc + vite → dist/
npm run typecheck    # tsc --noEmit
npm test             # Vitest unit tests
npm run test:e2e     # Playwright smoke tests
```

---

## Backend

**Stack:** Python 3.11 + FastAPI + Uvicorn + Pandas + Starlark + google-genai

### Backend layout

```
backend/
  app/
    main.py              FastAPI app factory + lifespan (MCP + scheduler)
    database.py          SQLite/MySQL — users, chats, runs, workflows, automations
    scheduler.py         Cron/interval automation runner (10s poll loop)
    routers/
      run.py             POST /run, POST /run/stream (SSE)
      validate.py        POST /validate
      copilot.py         Copilot generate/chat/explain + /node-manifest
      workflows.py       Workflow + draft CRUD
      library.py         Skills, data sources, run logs, audit logs
      auth.py            Email/password + Google OAuth + demo login
      automations.py     CRUD automations + manual trigger + run history
      agent.py           Agent metrics endpoint
    schemas.py           Pydantic request/response models
    deps.py              Shared dependencies (paths, singletons)
    mcp_lifecycle.py     Auto-start MCP bridge subprocess

  engine/
    dag_runner.py        Core: topo sort + execute nodes
    registry.py          Auto-discover NodeSpecs from nodes/
    node_spec.py         NodeSpec dataclass + YAML loader
    ports.py             PortSpec, ParamSpec, Widget enums
    validator.py         Deterministic graph validator
    orchestrator_runtime.py   Upstream output injection (incoming)
    starlark_sandbox.py  Hermetic Starlark execution
    context.py           RunContext (datasets, values, shared state)
    nodes/               Active node handlers (YAML + PY pairs)

  generation/
    harness/
      runner.py          AgentRunner control loop
      state.py           AgentState, AgentEvent, AgentPhase
      metrics.py         AgentMetrics (counters)
      intent.py          Create vs edit classification
      retriever.py       good_examples + contract retrieval
      enrichment.py      Prompt context (datasets, skills)
      task_manager.py    Parallel pre-planning tasks
      blueprint_router.py Match studio demos → parallel task units
      compactor.py       Conversation history compaction
      overflow_guard.py  Token budget triggers
      subagent_permissions.py Profile-based gates
      retry_policy.py    Exponential backoff for LLM/API
      agent_profiles.py  build / plan / explore profiles
      memory.py          Structured runtime memory
    prompt_builder.py    LLM prompt construction
    planner.py           Gemini LLM wrapper
    canonicalizer.py     Type ID normalization
    validator_adapter.py Bridge to engine/validator
    repair/
      auto_fixer.py      Deterministic repairs
      feedback_builder.py Error formatting
    generation_guardrails.md  LLM rules doc

  connectors/
    metadata/*.yaml      Dataset column schemas
    registry.py          ConnectorRegistry, get_rows()
    sqlite_demo.py       SQLite demo data helpers

  integrations/mcp/      Live MCP tool implementations (GitHub, Jira, Confluence)

  llm/
    gemini_adapter.py    Unified Gemini API wrapper

  good_examples/         studio_01 … studio_15 (agent few-shot + e2e)
  mcp_bridge/            HTTP MCP demo server (Confluence, Jira, GitHub)
  copilot/               Workflow generator (streaming pipeline)
  contracts/             Generated node contracts JSON
  skills/                Domain skill library (markdown)
  workflows/             Legacy showcase copies (not used for few-shot)
  scripts/               gen_artifacts, benchmarks, converters
  deploy/                Cloud Build + Cloud Run configs
```

### Entrypoints

| File | Purpose | Used by |
|------|---------|---------|
| `app/main.py` | FastAPI app with routers | Direct import |
| `server.py` | Supervisor shim — re-exports app with `/api` prefix | `uvicorn server:app` (production) |
| `api.py` | Backwards-compat shim | Legacy scripts, `start.sh` |
| `main.py` | CLI runner — execute workflows from command line | `python main.py workflow.json` |

### API endpoints

| Method | Path | Router | Purpose |
|--------|------|--------|---------|
| POST | `/run` | run.py | Execute workflow (blocking) |
| POST | `/run/stream` | run.py | Execute workflow (SSE stream) |
| POST | `/validate` | validate.py | Validate DAG structure |
| GET | `/node-manifest` | copilot.py | Studio palette metadata |
| GET | `/contracts` | copilot.py | Node I/O contracts |
| POST | `/copilot/generate` | copilot.py | Generate workflow (blocking) |
| POST | `/copilot/generate/stream` | copilot.py | Generate workflow (SSE) |
| POST | `/copilot/chat` | copilot.py | Multi-turn chat |
| GET | `/copilot/skills` | copilot.py | Skill library index |
| GET | `/workflows` | workflows.py | List saved workflows |
| GET | `/drafts` | workflows.py | List draft workflows |
| GET | `/data-sources` | library.py | Dataset schemas |
| GET | `/skills` | library.py | Skill library |
| POST | `/auth/login` | auth.py | Email/password login |
| POST | `/auth/register` | auth.py | User registration |
| GET | `/auth/me` | auth.py | Current user |
| GET | `/agent/metrics` | agent.py | Harness metrics |
| POST | `/copilot/generate/stream` | copilot.py | Sherpa build (SSE) — edit mode supported |
| POST | `/copilot/explain-run/stream` | copilot.py | Post-run analysis (SSE) |
| GET | `/copilot/example-prompts` | copilot.py | Dynamic build/ask prompt chips |
| GET | `/copilot/guardrails` | copilot.py | Guardrail text for UI |
| GET/POST/DELETE | `/copilot/chats/*` | copilot.py | Persisted chat threads |
| GET/POST/DELETE | `/automations` | automations.py | Scheduled workflow runs |
| POST | `/automations/{id}/trigger` | automations.py | Manual automation run |

All paths above are prefixed with `/api` when served via `server.py`.

### Request lifecycle: POST /run/stream

```
1. Receive workflow JSON
2. Resolve mock CSV paths
3. Validate DAG (validator.py) — reject if invalid
4. Create RunContext
5. Topological sort nodes
6. For each node:
   a. Look up handler in NODE_HANDLERS
   b. Build incoming outputs (orchestrator_runtime)
   c. Emit SSE: node_start
   d. Call handler(node, ctx, incoming)
   e. Type-check output against declared ports
   f. Apply output to RunContext
   g. Emit SSE: node_complete (or node_error)
7. Emit SSE: workflow_complete
```

### Request lifecycle: POST /copilot/generate/stream

```
1. Receive scenario + optional current_workflow
2. Create AgentRunner
3. Stream AgentEvents as SSE:
   a. Understanding → parse scenario
   b. Planning → match skills, load contracts, optional parallel pre-tasks
   c. Generating → call Gemini LLM (Planner)
   d. Canonicalize → normalize type IDs
   e. Validate → deterministic checks
   f. Auto-fix → mechanical repairs (free)
   g. Critiquing → LLM repair (if needed, up to 3x)
   h. Finalizing → runtime smoke test
   i. Complete → return validated workflow
4. Auto-save draft to drafts/
```

---

## Engine internals

### DAG runner (`engine/dag_runner.py`)

The execution engine. Zero knowledge of specific node types.

1. **Topological sort** — validates acyclic, computes execution order.
2. **Execute** — walks nodes in order, calls handlers via `NODE_HANDLERS`.
3. **Port checking** — validates handler output matches declared ports.
4. **Event streaming** — yields `node_start`, `node_complete`, `node_error`.

### Registry (`engine/registry.py`)

Auto-discovers nodes at import time:

```
1. Walk engine/nodes/ → active Studio nodes
2. Collect NODE_SPEC from each module
3. Build: NODE_SPECS (dict), NODE_HANDLERS (dict)
4. Expose: all_specs(), studio_manifest(), contracts_document()
```

### Orchestrator runtime (`engine/orchestrator_runtime.py`)

Bridges handler signatures:

- `build_incoming_outputs()` — `{upstream_id: output_dict}` for each node
- `apply_output_to_ctx()` — merges output into RunContext (datasets, values)
- Branch-aware: condition nodes route `rows_true`/`rows_false` by edge handle

### Validator (`engine/validator.py`)

Deterministic checks before execution:

- Graph structure (acyclic, connected edges)
- Node types exist in registry
- Required params present
- Port wiring compatibility
- Field binding resolution against data source schemas
- Hard rules (domain-specific constraints)

### Starlark sandbox (`engine/starlark_sandbox.py`)

Hermetic execution for `code` node:

- No imports, filesystem, or network
- Injected globals: `input_data`, `rows`
- Script assigns `output` or `result`
- Uses the `starlark` Python package

---

## LLM layer

**File:** `backend/llm/gemini_adapter.py`

Single seam for all LLM calls. Two entry points:

| Method | Use case |
|--------|----------|
| `chat_turn(system, history, user)` | Multi-turn with history (copilot chat) |
| `single_shot(prompt, model)` | One-shot (agent node, summarization) |

Callers depend only on this adapter — swapping LLM vendors is a one-file change.

**Environment:** `GEMINI_API_KEY` or `GOOGLE_API_KEY` in `backend/.env`.

---

## Persistence layer

**File:** `backend/app/database.py`

| Backend | When |
|---------|------|
| SQLite (`backend/copilot_chats.db`) | Default — zero config |
| MySQL | When `DATABASE_URL` or `MYSQL_*` env vars set |

**Tables:** `users`, `user_sessions`, `copilot_chats`, `run_logs`, `workflows`, `automations`, `automation_runs`

On first startup with empty DB, no workflows are seeded from disk. Vetted Studio demos live in `backend/good_examples/` (read-only, used by Copilot retriever and e2e tests). User workflows are saved via the API into the `workflows` table.

See [Database guide](./database.md).

---

## Automations scheduler

**File:** `backend/app/scheduler.py`

- Started in FastAPI lifespan alongside MCP bridge
- Polls every 10 seconds for due automations
- **Cron:** 5-field expression, fires once per matching minute
- **Interval:** every N minutes within a duration window from `created_at`
- Executes workflow JSON from request body or saved `workflows` table entry
- Vetted demos for testing: `backend/good_examples/studio_*.json`
- Writes to `run_logs` and `automation_runs`

UI: Left nav → **Automations** drawer.

---

## MCP bridge

**Directory:** `backend/mcp_bridge/`

HTTP server exposing Confluence, Jira, and GitHub operations over a
Studio-compatible REST contract:

```
POST {MCP_SERVER_URL}/tools/{tool}/run
```

- **Demo mode** (`MCP_BRIDGE_MODE=demo`) — returns mock data, no tokens needed.
- **Live mode** — requires `ATLASSIAN_*` / `GITHUB_*` env vars or per-node tokens.
- Auto-started by `app/mcp_lifecycle.py` when a workflow containing MCP nodes runs.

---

## Deployment

### Local development

```bash
./start.sh
# Kills any existing processes on :8001/:3000
# Starts backend (uvicorn) + frontend (vite dev)
# Opens http://localhost:3000
```

### Docker

```bash
# Backend
docker build -t dbsherpa-backend -f backend/Dockerfile backend
docker run --rm -p 8080:8080 -e GEMINI_API_KEY=$KEY dbsherpa-backend

# Frontend
docker build -t dbsherpa-frontend -f frontend/Dockerfile frontend
docker run --rm -p 8080:8080 -e BACKEND_URL=http://backend:8080 dbsherpa-frontend
```

### Cloud Run (GCP)

Config in `backend/deploy/` and `frontend/deploy/`:

- `cloudbuild.yaml` — Cloud Build pipeline
- `service.yaml` — Cloud Run service definition

Frontend image uses nginx to serve static files and reverse-proxy `/api/*`
to the backend URL (set via `BACKEND_URL` env var at deploy time). Same image
promotes through dev/staging/prod by changing one env var.

---

## Data flow summary

```
                    ┌──────────┐
                    │  Studio  │
                    │    UI    │
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              v          v          v
         POST /run   POST /copilot  GET /node-manifest
              │      /generate      │
              v          │          v
         ┌────────┐      │     ┌─────────┐
         │Validate│      │     │Registry │
         └───┬────┘      │     │manifest │
             │           v     └─────────┘
             v      ┌─────────┐
         ┌────────┐ │  Agent  │
         │  DAG   │ │ Harness │
         │ Runner │ │(Gemini) │
         └───┬────┘ └────┬────┘
             │           │
     ┌───────┼───────┐   │
     v       v       v   v
  ┌──────┐┌──────┐┌──────┐
  │ Node ││ Node ││Valid- │
  │  A   ││  B   ││ated  │
  │      ││      ││ DAG  │
  └──┬───┘└──┬───┘└──────┘
     │       │
     v       v
  ┌─────────────┐
  │  RunContext  │
  │  (datasets,  │
  │   values)    │
  └──────┬──────┘
         │
         v
  ┌─────────────┐
  │   Output    │
  │  (Excel,    │
  │   CSV, MCP) │
  └─────────────┘
```
