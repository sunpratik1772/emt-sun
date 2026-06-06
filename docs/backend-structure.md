# Backend package structure

> **May 2026 restructure** — enterprise layout with **no legacy shims**. Import from canonical paths only.

---

```
backend/
├── connectors/              Data catalog + connector implementations
│   ├── catalog.py           DataSourceRegistry, schema loading
│   ├── registry.py          ConnectorRegistry, get_rows()
│   ├── *_connector.py       csv, sqlite, solr, oracle backends
│   └── metadata/*.yaml      One YAML per dataset (column schemas)
│
├── integrations/mcp/        Live MCP tool implementations
│   ├── github/              connectivity.py + tools.py
│   ├── jira/
│   ├── confluence/
│   ├── credentials.py       Shared auth helpers
│   └── registry.py          Tool lookup for engine nodes
│
├── generation/              Copilot workflow generation
│   ├── harness/             AgentRunner, intent, retriever, memory, …
│   ├── repair/              AutoFixer, FeedbackBuilder
│   ├── planner.py           Gemini wrapper
│   ├── prompt_builder.py    System + repair prompts
│   ├── validator_adapter.py Bridge to engine/validator
│   └── generation_guardrails.md  LLM rules (also served to UI)
│
├── engine/
│   ├── dag_runner.py        Topological execution
│   ├── validator.py         Deterministic graph checks
│   └── nodes/               *.py + *.yaml node pairs (36 active)
│
├── mcp_bridge/              HTTP demo server (:8765)
│   └── server.py            POST /tools/{name}/run
│
├── copilot/                 SSE adapters, workflow finalize, preflight
├── app/                     FastAPI routers, database, scheduler
├── llm/                     GeminiAdapter
├── skills/                  Domain skill markdown for prompts
├── contracts/               Generated node I/O contracts JSON
├── good_examples/           studio_01 … studio_15 (agent few-shot demos)
└── scripts/                 gen_artifacts.py, reset_db.py, benchmarks
```

---

## Import paths

| Need | Import |
|------|--------|
| Data registry | `from connectors import get_registry, get_rows` |
| Harness runner | `from generation.harness.runner import AgentRunner` |
| Prompt builder | `from generation.prompt_builder import PromptBuilder` |
| Auto-fixer | `from generation.repair.auto_fixer import AutoFixer` |
| MCP tools (live) | `from integrations.mcp.registry import get_tool` |
| MCP HTTP (demo) | `python -m mcp_bridge.server` |

---

## Data vs app persistence

| Store | Path / module | Purpose |
|-------|---------------|---------|
| App DB | `backend/copilot_chats.db` (SQLite default) | Users, chats, saved workflows, run logs |
| Demo surveillance DB | `backend/demo_data/surveillance_fixture.sqlite` | `db_query` node fixture data |
| Dataset catalog | `connectors/metadata/*.yaml` | Column schemas for Copilot + `csv_extract` |

These are **separate**. Resetting the app DB does not remove `good_examples/` or connector metadata.

---

## Studio demos

| Location | Role |
|----------|------|
| `good_examples/studio_*.json` | Canonical vetted demos — used in harness retriever, e2e tests, prompt examples |
| `workflows/demo_showcase/` | Older copies; not used for agent few-shot |
| `workflows` DB table | User-saved workflows (seeded empty; not from `good_examples/`) |

---

## Design principles

| Principle | How we apply it |
|-----------|-----------------|
| **DRY** | One harness in `generation/`; shared `AtlassianTransport`; single metadata catalog |
| **SRP** | Connectors = data; integrations/mcp = external tools; mcp_bridge = HTTP demo only |
| **KISS** | Node = YAML spec + Python handler; registry auto-discovers at import |
| **YAGNI** | No `agent/` or `data_sources/` shims; Solr/Oracle connectors are thin stubs + YAML templates |

See [Architecture](./architecture.md) for request flows and API routes.
