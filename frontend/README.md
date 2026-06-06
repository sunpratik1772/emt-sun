# Sherpa Studio UI

React frontend for **dbSherpa Studio** — workflow editor, Copilot, library drawers, and run output.

**Architecture:** See [docs/frontend-architecture.md](../docs/frontend-architecture.md) for module layout, global patterns, and conventions.

---

## Prerequisites

- Node.js 18+
- Backend running on port **8001** (or use `./start.sh` from repo root)

---

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Vite dev server at http://localhost:3000 |
| `npm start` | Same as dev, binds `0.0.0.0:3000` |
| `npm run build` | Typecheck + production build → `dist/` |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest unit tests |
| `npm run test:e2e` | Playwright smoke tests (starts dev server) |
| `npm run preview` | Serve production build locally |

---

## Project structure (quick reference)

```
src/
  main.tsx              Router, QueryClient, auth routes
  App.tsx               Studio shell (5 regions)
  components/           Feature UI (canvas, panels, drawers, copilot)
  store/                Zustand stores + workflow slices
  hooks/                TanStack Query + UI hooks
  services/api.ts       All REST + SSE calls
  nodes/                Generated node manifest
```

---

## Dev proxy

Vite proxies `/api/*` to `http://localhost:8001`. No CORS setup needed in local dev.

---

## Code splitting

Heavy dependencies load on demand:

- **React Flow** — workflow canvas
- **Monaco** — code/YAML editor view
- **Copilot** — LLM panel

Vendor chunks configured in `vite.config.ts` (`reactflow`, `monaco`).

---

## Testing

```bash
npm test              # 18 unit tests (utils + slice helpers)
npm run test:e2e      # Login page + auth redirect
```

---

## Related docs

- [Frontend Architecture](../docs/frontend-architecture.md)
- [System Architecture](../docs/architecture.md)
- [Engineering Onboarding](../docs/engineering-onboarding.md)
