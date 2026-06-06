# dbSherpa Studio — PRD

## Original problem statement
Clone https://github.com/sunpratik1772/emt-sherp and finish building the
logs panel, copilot, align fonts to Cursor/Vercel/Linear/v0 style. Change
color scheme of skills, data sources and templates/workflows to match the
workflow page. Iteration 4 added: minimal half-hero login page with Google
auth + user initials avatar in the top-right; light-theme polish on
ReactFlow canvas.

## Architecture
- **Frontend:** React 18 + Vite + TypeScript + Tailwind + ReactFlow + Zustand
  + react-router-dom v7. Auth gated routes at /login, /dashboard.
- **Backend:** FastAPI port 8001, mounted under `/api`. Routers:
  workflows, copilot, library, run, validate, reports, agent, **auth**.
- **Auth:** Emergent-managed Google OAuth.
  Endpoints: `POST /api/auth/session`, `GET /api/auth/me`, `POST /api/auth/logout`.
  Storage: Mongo `users` (custom user_id UUID, never `_id`) + `user_sessions`
  (7-day TTL). Session token in httpOnly Secure SameSite=None cookie at `/`.
- **LLM:** `emergentintegrations.LlmChat` w/ Emergent Universal LLM key,
  default model `gemini-2.5-flash`.
- **Logs:** JSONL files in `/tmp/dbsherpa/logs/`.

## What's been implemented (cumulative)
1. Cloned upstream repo + deps.
2. LLM adapter on Emergent Universal Key (gemini-2.5-flash).
3. Audit log subsystem + run-stream logging gap fix.
4. Logs Drawer rebuilt: Run logs / Audit tabs.
5. Copilot Build/Edit/Ask toggle. Streaming Ask mode (SSE).
6. Color scheme neutralized (off-white dark / slate light).
7. Templates drawer minimalistic; "TEMPLATES" header.
8. Run button icon-only.
9. Light-theme contrast pass (text-3, borders, bg-3, panel-glass alpha).
10. **Auth (this iteration):**
    - `/login` half-hero page (left: hero + "Start building" CTA;
      right: "Continue with Google" card). Both kick off Emergent OAuth.
    - `/dashboard` is the workspace, gated by `<ProtectedRoute>`.
    - `AuthCallback` exchanges `#session_id=…` for a session token
      synchronously during render to avoid a race with `/auth/me`.
    - Topbar avatar shows user initials (Geist letter-spacing); click
      opens a popover with full name/email + Sign out.
    - CORS switched to `allow_origin_regex=".*"` + `allow_credentials=True`
      so the cookie ride-along works.
11. **Light-theme canvas polish:**
    - `Tag` chips swapped from hardcoded indigo to CSS-variable tones
      so they invert with the theme.
    - Node handles' inner border now uses `--bg-node` (was `--bg-0`)
      so the punched-out look survives both themes.

## Backlog (P1)
- Bundled workflow templates fail validation on `{stats}` ref (upstream).
- Email allowlist on `/api/auth/session` if multi-tenant.

## Future
- Persist run/audit logs in MongoDB.
- Filter/search inside Audit panel.
- Model picker in Copilot header.
- Per-user workflow scoping (every workflow belongs to a user_id).
