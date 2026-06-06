# Sherpa Studio (dbSherpa)

Visual workflow studio: DAG editor, Starlark **code** transforms, Gemini **agent** nodes, **MCP** integrations (Confluence, Jira, GitHub), and **sherpa** — the AI copilot that generates validated workflows from plain English.

**Public repo:** [github.com/sunpratik1772/sherpa-co-latest](https://github.com/sunpratik1772/sherpa-co-latest)

---

## Documentation

**Start here:** [docs/README.md](./docs/README.md)

| Guide | Audience |
|-------|----------|
| **[Engineering Onboarding](./docs/engineering-onboarding.md)** | New engineers — setup, codebase, core concepts |
| **[Architecture](./docs/architecture.md)** | System diagrams, API routes, data flows |
| **[Node Catalogue](./docs/node-catalogue.md)** | All **36** nodes — params, ports, selection guide |
| **[Creating Nodes](./docs/creating-nodes.md)** | Adding a node end-to-end |
| **[Data Source Onboarding](./docs/data-source-onboarding.md)** | Datasets and schemas |
| **[Generation Harness](./docs/generation-harness.md)** | Copilot internals — runner, planner, auto-fixer |
| **[Sherpa Harness Onboarding](./docs/sherpa-agent-harness-onboarding.md)** | Full Sherpa decision map — routes, APIs, UI, plan modal, metadata |
| **[Backend Structure](./docs/backend-structure.md)** | Package layout and import paths |
| **[Database](./docs/database.md)** | Auth, chat history, automations, run logs |

Studio demos: `backend/good_examples/studio_*.json` (15 vetted workflows)

---

## Quick start

### First-time setup

```bash
cd frontend && npm install && cd ..
pip install -r backend/requirements.txt   # use a venv if you prefer

echo 'GEMINI_API_KEY=your_key_here' > backend/.env
# Optional: ATLASSIAN_* / GITHUB_* for live MCP — see docs/README.md
```

| Prerequisite | Notes |
|--------------|--------|
| **Node.js + npm** | Frontend (Vite on port 3000) |
| **Python 3** | Backend (FastAPI on port 8001) |
| **`GEMINI_API_KEY`** | Required for agent nodes + Sherpa Copilot |

### Start the app

```bash
./start.sh
```

| Service | URL |
|---------|-----|
| UI | http://localhost:3000 |
| API | http://localhost:8001/api/health |

Logs: `.run/logs/backend.log`, `.run/logs/frontend.log`

Open the Studio, load a workflow (e.g. `studio_10_leads_tier_mcp_publish.json`), and **Run**.

### What `./start.sh` does

1. Stops anything already listening on ports **8001** and **3000**
2. Starts the backend (`uvicorn server:app`)
3. Starts the frontend (`npm start` / Vite)
4. Opens http://localhost:3000 in your browser

On backend startup, `init_db()` runs automatically and creates the **app SQLite schema** in `backend/copilot_chats.db` if it does not exist yet (`workflows`, `drafts`, `run_logs`, `automations`, `copilot_chats`, etc.).

### What `./start.sh` does **not** do

| Step | When you need it |
|------|------------------|
| `npm install` | Once, before the first frontend run |
| `pip install -r backend/requirements.txt` | Once, before the first backend run |
| Create `backend/.env` | Before using Sherpa or agent nodes |
| `python3 backend/scripts/gen_sqlite_demo_data.py` | Only if you change demo connector schemas |

### Local databases (two separate files)

| File | Purpose |
|------|---------|
| `backend/copilot_chats.db` | App data — saved workflows, drafts, runs, automations, chat history. **Auto-created** on first backend start. |
| `backend/demo_data/surveillance_fixture.sqlite` | Demo tables for `db_query` nodes (`hs_trades`, alerts, etc.). **Shipped in the repo**; regenerate with `gen_sqlite_demo_data.py` only when needed. |

To fully reset app data, delete `backend/copilot_chats.db` and restart — tables are recreated empty. See [Database guide](./docs/database.md) for schema details.
