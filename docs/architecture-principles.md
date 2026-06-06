# Architecture principles

How the backend restructure (May 2026) maps to common design goals. Target: **8–9/10** on each axis.

| Principle | Score | Notes |
|-----------|-------|-------|
| **GRASP** | **8/10** | High cohesion per package (`connectors`, `generation`, `integrations/mcp`). Controller pattern in FastAPI routers; `AgentRunner` orchestrates generation without owning validation logic. |
| **DRY** | **8/10** | Shared `AtlassianTransport` for Jira + Confluence; single metadata catalog in `connectors/metadata/`; one harness implementation in `generation/`. Demo MCP handlers in `mcp_bridge/tools.py` vs live handlers in `integrations/` — intentional demo/live split. |
| **KISS** | **9/10** | Node = paired `.yaml` + `.py`; registry auto-discovers handlers; connector onboarding = copy YAML template + edit columns. |
| **SOLID** | **8/10** | Connectors implement a small `TableBinding` interface; MCP split by provider; generation harness depends on abstractions (`ValidatorAdapter`, `Planner`) not concrete engine internals. |
| **YAGNI** | **9/10** | Removed legacy `agent/`, `data_sources/`, unused harness re-export trees, MCP client shims. Solr/Oracle connectors are stubs + YAML templates (onboarding contract, not fake full implementations). |

---

## Package boundaries

```
connectors/     → "What data exists?" (schemas, demo rows, live query hooks)
generation/     → "How does Copilot build workflows?" (runner, prompts, repair)
integrations/   → "How do we call external APIs?" (MCP tool implementations)
engine/         → "How do workflows execute?" (DAG runner, nodes, validator)
copilot/        → "How does the UI talk to generation?" (SSE, preflight, finalize)
mcp_bridge/     → "How do demos run without live creds?" (HTTP tool server)
app/            → "How does HTTP reach the above?" (routers, DB, scheduler)
```

**Rule:** Production code imports `connectors`, `generation`, and `integrations.mcp` — never deleted legacy paths.

---

## Verification

Structural changes are done when:

1. `pytest tests/test_studio_workflows_e2e.py` — all 15 `good_examples/studio_*.json` pass.
2. `pytest tests/test_harness_prompt_scenarios.py -m integration` — live Gemini scenarios pass.
3. `rg 'from agent\.|from data_sources'` over `backend/` returns no production imports.

See [Backend Structure](./backend-structure.md) for the directory tree.
