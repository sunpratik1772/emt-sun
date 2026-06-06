# Gemini LLM Migration Guide

> How dbSherpa Studio talks to Gemini today, how to configure credentials, and how to
> migrate from **Google AI API keys** to **Vertex AI** without touching Sherpa, harness,
> or workflow code.
>
> **Last updated:** June 2026

---

## Summary

All backend LLM traffic goes through **one module**:

| Layer | Location |
|-------|----------|
| Public API | `backend/llm/__init__.py` |
| Implementation | `backend/llm/gemini_adapter.py` |

Every caller imports from `llm` and uses:

- `get_default_adapter()` — process-wide singleton
- `gemini_configured()` — credential probe (no network)
- `gemini_api_key()` — primary key resolution (API-key mode)
- `llm_provider()` — `"gemini"` or `"vertex"`
- `probe_gemini_connection()` — hello-world connectivity test

The frontend **never** calls Gemini. It only talks to the backend API.

---

## Architecture

```mermaid
flowchart LR
  subgraph callers [Callers — import from llm only]
    Sherpa[copilot/*]
    Harness[generation/*]
    AgentNode[engine/nodes/agent.py]
    Health[/api/agent/llm/*]
  end

  subgraph seam [Single seam]
    Init[llm/__init__.py]
    Adapter[gemini_adapter.py]
    Singleton[get_default_adapter]
    ClientCache[_CLIENT_CACHE]
    SDK[google.genai.Client]
  end

  Sherpa --> Init
  Harness --> Init
  AgentNode --> Init
  Health --> Init
  Init --> Singleton
  Singleton --> Adapter
  Adapter --> ClientCache
  ClientCache --> SDK
```

### Rules (do not break these)

1. **Never** `from google import genai` outside `gemini_adapter.py`.
2. **Never** construct `GeminiAdapter()` in application code — use `get_default_adapter()`.
3. **Never** read `GEMINI_API_KEY` directly for LLM calls — use `gemini_configured()` or the adapter.
4. Tests may call `reset_llm_runtime_for_tests()` to clear the singleton and client cache.

Swapping API keys for Vertex credentials is intentionally a **one-file change** in
`gemini_adapter.py` (`_create_sdk_client`).

---

## Current setup: Google AI API keys

### Minimum local config

Create or edit `backend/.env`:

```env
GEMINI_API_KEY=your_key_here
```

Restart the backend after changing env vars.

### Verify locally

```bash
# Credential presence (no network)
curl -s http://localhost:8001/api/agent/llm/health | jq

# Live hello-world call via shared adapter
curl -s http://localhost:8001/api/agent/llm/probe | jq

# Process health (includes llm.configured)
curl -s http://localhost:8001/api/health | jq
```

Expected health response:

```json
{
  "configured": true,
  "provider": "gemini"
}
```

Expected successful probe:

```json
{
  "ok": true,
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "message": "ok",
  "latency_ms": 450.2
}
```

### Run the live connectivity test

```bash
cd backend
pytest tests/test_gemini_connectivity.py -q
```

---

## API key rotation and failover

The adapter supports up to **three API keys** plus a legacy fallback. On rate limits,
auth failures, or transient 5xx errors it automatically tries the next key.

| Env var | Role |
|---------|------|
| `GEMINI_API_KEY` | Primary key |
| `GEMINI_API_KEY_2` | First backup |
| `GEMINI_API_KEY_3` | Second backup |
| `GOOGLE_API_KEY` | Legacy fallback (read only if primary keys are set via adapter config) |

Example multi-key `.env`:

```env
GEMINI_API_KEY=primary_key
GEMINI_API_KEY_2=backup_key
GEMINI_API_KEY_3=overflow_key
```

SDK clients are **cached per key** (not per request), so rotation does not create a
new client on every call.

---

## Migration: API keys → Vertex AI

Vertex mode uses **Application Default Credentials** (ADC) — service account on Cloud Run,
`gcloud auth application-default login` locally — instead of `GEMINI_API_KEY`.

### Step 1 — Enable Vertex in GCP

1. Enable the **Vertex AI API** on your GCP project.
2. Grant the runtime service account `roles/aiplatform.user` (or tighter custom role).
3. Confirm the model you need (default: `gemini-2.5-flash`) is available in your region.

### Step 2 — Update environment

In `backend/.env` (local) or Cloud Run / Secret Manager (production):

```env
LLM_PROVIDER=vertex
VERTEX_PROJECT=your-gcp-project-id
VERTEX_LOCATION=us-central1
```

You may **remove** `GEMINI_API_KEY*` when fully on Vertex. `gemini_configured()` returns
true when `VERTEX_PROJECT` is set.

Local ADC setup:

```bash
gcloud auth application-default login
export LLM_PROVIDER=vertex
export VERTEX_PROJECT=your-gcp-project-id
export VERTEX_LOCATION=us-central1
```

### Step 3 — Restart and verify

```bash
curl -s http://localhost:8001/api/agent/llm/health | jq
curl -s http://localhost:8001/api/agent/llm/probe | jq
```

Expect `"provider": "vertex"` and `"ok": true` on probe.

### Step 4 — Run regression tests

```bash
cd backend
pytest tests/test_gemini_connectivity.py -q
pytest tests/test_studio_workflows_e2e.py -q
pytest tests/test_harness_prompt_scenarios.py -m integration -q
```

Agent nodes and Sherpa harness paths all use the same adapter — no code changes required
in `copilot/`, `generation/`, or `engine/nodes/agent.py`.

---

## Cloud Run / production deployment

See also [backend/deploy/README.md](../backend/deploy/README.md).

### API key mode (today)

Store the key in Secret Manager and mount it as `GEMINI_API_KEY` on the service
(`backend/deploy/service.yaml` documents the secret name `gemini-api-key`).

### Vertex mode

1. Set `LLM_PROVIDER=vertex`, `VERTEX_PROJECT`, `VERTEX_LOCATION` as plain env vars.
2. Attach a service account with Vertex permissions — **no** Gemini API key secret needed.
3. Redeploy and hit `/api/agent/llm/probe` from inside the VPC or via your ingress.

### Rollback

Switch back instantly:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
```

Unset or leave `VERTEX_PROJECT` empty. Restart the process.

---

## Default model

Defined once in `gemini_adapter.py`:

```python
DEFAULT_MODEL = "gemini-2.5-flash"
```

Workflow **agent** nodes may override `model` in node params; Sherpa and harness calls
use the adapter default unless a call site passes an explicit `model=` argument.

To change the fleet-wide default, edit `DEFAULT_MODEL` in `gemini_adapter.py` only.

---

## Who calls Gemini?

All paths below use `get_default_adapter()` (or accept an injected adapter in tests):

| Area | Module |
|------|--------|
| Sherpa routing | `copilot/llm_router.py` |
| Workflow generation | `copilot/workflow_generator.py`, `generation/planner.py` |
| Strict compile / repair | `copilot/strict_compiler.py` |
| Run analysis | `copilot/run_analyst.py` |
| Thinking monologue | `copilot/thinking_monologue.py` |
| Example prompts / dashboard subline | `copilot/prompt_examples.py`, `copilot/dashboard_subline.py` |
| Intent clarification | `copilot/intent_clarification.py` |
| Schedule parsing | `copilot/schedule_parser.py` |
| Harness parallel runner | `generation/harness/runner.py` |
| Workflow agent node | `engine/nodes/agent.py` |
| Health / probe | `app/routers/agent.py`, `server.py` |

If you add a new LLM feature, import from `llm` and call `get_default_adapter()`.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `configured: false` on `/api/agent/llm/health` | `GEMINI_API_KEY` in `backend/.env`, or `VERTEX_PROJECT` when `LLM_PROVIDER=vertex` |
| Probe returns 401 / 403 | Key invalid or Vertex SA missing `aiplatform.user` |
| Probe returns 429 | Enable `GEMINI_API_KEY_2` / `_3` or reduce parallel harness tests |
| Agent node fails at run time | Same as probe — backend env, not frontend |
| "Gemini unavailable" in Sherpa | `gemini_configured()` is false; heuristic fallbacks run instead |
| Tests pass locally but fail in CI | CI may use `mock_key_for_testing` from `conftest.py`; live tests need real key |

Backend logs on first LLM use:

```
LLM adapter ready (provider=gemini, model=gemini-2.5-flash)
```

---

## Migration checklist

- [ ] Confirm all env vars in target environment (`backend/.env` or Cloud Run)
- [ ] `GET /api/agent/llm/health` → `configured: true`
- [ ] `GET /api/agent/llm/probe` → `ok: true`
- [ ] `pytest tests/test_gemini_connectivity.py -q`
- [ ] Open Studio → Sherpa → send a build prompt
- [ ] Run a workflow with an **AI Agent** node
- [ ] (Vertex) Remove unused `GEMINI_API_KEY` secrets after soak period
- [ ] (Vertex) Confirm billing/project quotas in GCP console

---

## Related docs

- [Engineering Onboarding](./engineering-onboarding.md) — local setup
- [Sherpa Agent Harness](./generation-harness.md) — Copilot generation pipeline
- [Backend Structure](./backend-structure.md) — package layout
- [Deploy README](../backend/deploy/README.md) — Cloud Run secrets and service YAML
