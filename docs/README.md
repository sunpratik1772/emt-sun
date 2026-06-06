# dbSherpa Studio — Docs

Technical reference for **engineers**, **AI agents extending this repo**, and **Sherpa (Copilot)** generating workflows in the Studio UI.

**Repository:** [github.com/sunpratik1772/sherpa-latest](https://github.com/sunpratik1772/sherpa-latest)

---

## Start here

| Doc | Who it's for | What you'll learn |
|-----|--------------|-------------------|
| **[Engineering Onboarding](./engineering-onboarding.md)** | New engineers | Setup, repo tour, core concepts, day-one tasks |
| **[Architecture](./architecture.md)** | All engineers | System diagrams, frontend/backend, API routes, deployment |
| **[Backend Structure](./backend-structure.md)** | Backend contributors | Canonical package layout and import paths |
| **[Frontend Architecture](./frontend-architecture.md)** | Frontend contributors | Module map, Zustand slices, TanStack Query, global patterns |
| **[Node Catalogue](./node-catalogue.md)** | Workflow authors | All **36** Studio nodes — params, ports, when to use each |
| **[Creating Nodes](./creating-nodes.md)** | Platform engineers | Add a node end-to-end (YAML + handler + artifacts) |
| **[Data Source Onboarding](./data-source-onboarding.md)** | Data engineers | Register datasets in `connectors/` for `csv_extract` / `db_query` |
| **[Sherpa Agent Harness](./generation-harness.md)** | Copilot contributors | Routing, clarification, follow-ups, UI stream, AgentRunner, SSE, tests |
| **[Sherpa Harness Onboarding](./sherpa-agent-harness-onboarding.md)** | Senior engineers / fast ramp | Full decision map: intents, APIs, UI state, plan modal, metadata, debugging |
| **[MCP Integrations](./mcp-integrations.md)** | Integration engineers | GitHub/Jira/Confluence creds, bridge endpoints & tools, Teams/Outlook |
| **[Database](./database.md)** | Backend / ops | SQLite/MySQL overview, ops, scheduler |
| **[DB scripts & relations](./db/README.md)** | Backend / ops | Canonical SQL (v5), ER diagram, Cloud SQL setup |
| **[Gemini Migration](./gemini-migration.md)** | Backend / ops | Single LLM seam, API keys, Vertex AI migration, health probes |

---

## In-repo references

| Resource | Location |
|----------|----------|
| Studio demo workflows (agent few-shot) | `backend/good_examples/studio_*.json` (15 files) |
| Legacy showcase copies | `backend/workflows/demo_showcase/` |
| Auto-generated node list | `node_detail.md` (run `python backend/scripts/gen_artifacts.py`) |
| MCP bridge setup | [MCP Integrations](./mcp-integrations.md) · [backend/mcp_bridge/README.md](../backend/mcp_bridge/README.md) |
| Connector quick start | [backend/connectors/README.md](../backend/connectors/README.md) |
| Generation guardrails (LLM) | `backend/generation/generation_guardrails.md` |
| Skill library | `backend/skills/*.md` |

---

## Quick start (local)

```bash
git clone https://github.com/sunpratik1772/sherpa-latest.git
cd sherpa-latest
./start.sh
```

| Service | URL |
|---------|-----|
| **Studio UI** | http://localhost:3000 |
| **Backend API** | http://localhost:8001/api/health |
| **MCP bridge** | http://localhost:8765/health (auto-started) |

### Minimum configuration

Create `backend/.env`:

```env
GEMINI_API_KEY=your_key_here
```

Optional integrations:

```env
GITHUB_TOKEN=...
ATLASSIAN_EMAIL=...
ATLASSIAN_API_TOKEN=...
TEAMS_INCOMING_WEBHOOK_URL=...
SOLR_URL=...
ORACLE_DSN=...
```

---

## Definition of done (backend changes)

After structural or harness changes, run:

```bash
cd backend
pytest tests/test_studio_workflows_e2e.py -q
pytest tests/test_harness_prompt_scenarios.py -m integration -q   # requires GEMINI_API_KEY
```

All **15** `good_examples/studio_*.json` workflows must validate and execute (live Gemini for `agent` nodes).

---

## Import paths (canonical)

| Need | Import |
|------|--------|
| Data registry | `from connectors import get_registry, get_rows` |
| Harness | `from generation.harness.runner import AgentRunner` |
| MCP live tools | `from integrations.mcp.registry import get_tool` |
| MCP HTTP server | `python -m mcp_bridge.server` |

Do **not** import from removed packages (`agent`, `data_sources`).

---

## Docs in the UI

The Studio **Docs** page loads guides from `GET /api/docs`, which reads markdown from this `docs/` folder. Edit guides here; the API strips the leading `# Title` before serving content to the frontend.
