"""
dbSherpa FastAPI app.

Routers are intentionally one-per-concern so different engineers can own
and evolve them independently without stepping on each other:

    /workflows       → app.routers.workflows   (saved CRUD)
    /drafts          → app.routers.workflows   (scratch CRUD + promote)
    /run, /run/stream→ app.routers.run         (DAG execution)
    /validate        → app.routers.validate    (deterministic DAG validation)
    /report/*        → app.routers.reports     (generated xlsx downloads)
    /copilot/*       → app.routers.copilot     (LLM generation + skills)
    /contracts       → app.routers.copilot     (node schemas)
    /agent/*         → app.routers.agent       (harness metrics + introspection)

All cross-cutting plumbing (CORS, logging, shared state like the
copilot singleton) lives here. Nothing domain-specific.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from runtime_env import ensure_env_loaded

# Load backend/.env before any code reads os.environ (Gemini, MCP, output dirs, etc.).
ensure_env_loaded()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import agent as agent_routes
from .routers import auth as auth_routes
from .routers import automations as automations_routes
from .routers import user as user_routes
from .routers import copilot as copilot_routes
from .routers import docs as docs_routes
from .routers import library as library_routes
from .routers import reports as reports_routes
from .routers import run as run_routes
from .routers import validate as validate_routes
from .routers import workflows as workflow_routes
from .routers import workspace as workspace_routes
from .routers import code_graph as code_graph_routes

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from .mcp_lifecycle import ensure_mcp_bridge, stop_mcp_bridge
    from .scheduler import start_scheduler, stop_scheduler

    ensure_mcp_bridge()
    start_scheduler()
    yield
    stop_mcp_bridge()
    stop_scheduler()


app = FastAPI(title="dbSherpa API", version="1.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {"service": "dbSherpa", "status": "running", "version": app.version}


app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(automations_routes.router)
app.include_router(workflow_routes.router)
app.include_router(workflow_routes.drafts_router)
app.include_router(run_routes.router)
app.include_router(validate_routes.router)
app.include_router(reports_routes.router)
app.include_router(copilot_routes.router)
app.include_router(copilot_routes.contracts_router)
app.include_router(agent_routes.router)
app.include_router(library_routes.router)
# Served at `/api/docs` (Vite proxy). Do not mount at `/docs` — FastAPI reserves that for Swagger UI.
app.include_router(docs_routes.router, prefix="/api")
app.include_router(workspace_routes.router)
app.include_router(code_graph_routes.router, prefix="/api")
