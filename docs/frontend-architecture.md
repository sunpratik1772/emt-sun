# Frontend Architecture

> dbSherpa Studio UI (`frontend/`) — module layout, global patterns, data flow, and conventions.
> Last updated: May 2026 (post Vite migration + store/query refactor).

---

## Summary

The frontend is a **Vite + React 18 + TypeScript** single-page app. Cross-cutting concerns are centralized:

| Concern | Global home |
|---------|-------------|
| HTTP / SSE | `services/api.ts` |
| Server cache (library drawers) | TanStack Query — `hooks/useLibraryQueries.ts` + `hooks/queryKeys.ts` |
| Editor / run / copilot state | Zustand — `store/workflowStore.ts` + `store/workflow/*` slices |
| Auth session | `store/authStore.ts` |
| Theme | `store/themeStore.ts` |
| Notifications | `store/toastStore.ts` + `components/ToastHost.tsx` |
| Node palette metadata | `store/nodeRegistryStore.ts` + `nodes/generated.ts` |
| Left-nav drawer routing | `store/studioSectionStore.ts` |
| Errors (UI regions) | `components/ErrorBoundary.tsx` |
| Modal a11y | `components/Modal.tsx` + `hooks/useFocusTrap.ts` |

**Honest status:** The active application code is structured and consistent. A few **migration leftovers** remain on disk (unused shadcn `components/ui/*.jsx`, legacy barrels) — they are not imported and safe to delete in a follow-up cleanup PR. Some large feature files (Topbar, AutomationsDrawer, ConfigView, Copilot) are functional but not yet split into submodules.

---

## Stack

| Layer | Choice |
|-------|--------|
| Build | Vite 5, TypeScript 5 |
| UI | React 18, Tailwind CSS, Lucide icons via `icons/arc.tsx` |
| Canvas | React Flow 11 |
| Code view | Monaco (`@monaco-editor/react`) |
| State | Zustand 4 (multiple stores + composed workflow store) |
| Server state | TanStack Query 5 (library/automation/copilot lists) |
| Routing | React Router 7 |
| Tests | Vitest (unit), Playwright (E2E smoke) |

---

## Directory map

```
frontend/
├── index.html                 Vite HTML shell
├── vite.config.ts             Dev proxy, path aliases, manualChunks, Vitest
├── playwright.config.ts       E2E (auto-starts Vite dev server)
├── e2e/smoke.spec.ts          Login + auth redirect smoke tests
└── src/
    ├── main.tsx               Bootstrap: QueryClient, Router, top ErrorBoundary
    ├── App.tsx                Studio shell layout (5 regions + drawers)
    │
    ├── pages/                 Route-level screens (outside studio shell)
    │   ├── LoginPage.tsx
    │   ├── AuthCallback.tsx
    │   └── docs/DocsPage.tsx  (lazy-loaded)
    │
    ├── components/            Feature UI
    │   ├── WorkflowCanvas/    React Flow editor, validation badges, DnD
    │   ├── WorkflowCodeEditor/ Monaco YAML/JSON editor
    │   ├── WorkflowDrawer/    Saved workflows + drafts library
    │   ├── RightPanel/        Config, run log, output, copilot host
    │   ├── Copilot/           LLM chat (lazy-loaded from RightPanel)
    │   ├── drawers/           Library section drawers (Skills, Data, Runs, Nodes, Automations)
    │   ├── NodePanel/         Node palette + ⌘K search
    │   ├── Topbar/            Run, save, validate, import/export
    │   ├── LeftNav.tsx        Primary navigation + section triggers
    │   ├── ActivityRail.tsx   Right-rail panel mode toggles
    │   ├── BottomOutputPanel.tsx  Resizable run output footer
    │   ├── ToastHost.tsx      Global toast renderer
    │   ├── Modal.tsx          Focus-trapped dialogs
    │   ├── ErrorBoundary.tsx  Regional error recovery
    │   ├── AsyncFallback.tsx  Suspense loading chrome
    │   └── ui/*.jsx           ⚠ Legacy shadcn — NOT imported (dead)
    │
    ├── store/
    │   ├── workflowStore.ts   Composes workflow slices (public API)
    │   ├── workflow/
    │   │   ├── types.ts         Full WorkflowStore contract
    │   │   ├── workflowSlice.ts DAG editing, undo history, selection
    │   │   ├── runStream.ts     SSE run queue + per-node status
    │   │   ├── copilotSlice.ts  Chat messages, undo checkpoints
    │   │   ├── uiSlice.ts       Panels, panes, workspace chrome
    │   │   ├── paneUtils.ts     Pane size limits + helpers
    │   │   └── workflowHelpers.ts
    │   ├── authStore.ts
    │   ├── themeStore.ts
    │   ├── toastStore.ts
    │   ├── nodeRegistryStore.ts
    │   ├── studioSectionStore.ts
    │   ├── layout.ts            Auto-layout (not a Zustand store)
    │   ├── useDraftAutosave.ts
    │   └── useNodeRunStatus.ts
    │
    ├── hooks/
    │   ├── useLibraryQueries.ts TanStack Query hooks for library API
    │   ├── queryKeys.ts       Shared cache keys
    │   ├── useCompactStudio.ts  Responsive breakpoint (<1024px)
    │   └── useFocusTrap.ts
    │
    ├── services/
    │   └── api.ts             Single HTTP + SSE client
    │
    ├── nodes/
    │   ├── generated.ts       AUTO-GENERATED manifest (colors, icons, NodeType)
    │   ├── index.ts           Public node metadata API
    │   └── lucideIconMap.ts
    │
    ├── types/index.ts         Domain types (Workflow, RunResult, …)
    ├── lib/env.ts             DEMO_AUTH, PREVIEW_MODE flags
    └── styles/                Design tokens + ReactFlow overrides
```

---

## Application bootstrap

```
index.html
    └── main.tsx
            ├── QueryClientProvider (staleTime 30s, retry 1)
            ├── BrowserRouter
            │     └── ErrorBoundary (region="Application")
            │           └── AppRouter
            │                 ├── /login          → LoginPage
            │                 ├── /docs           → DocsPage (lazy)
            │                 ├── /dashboard      → ProtectedRoute → App
            │                 └── hash session_id → AuthCallback
            └── global CSS (linear-tokens, globals, agent-animations)
```

**Dev proxy:** Vite forwards `/api/*` to `http://localhost:8001`. SSE run stream has a dedicated proxy rule with `Accept-Encoding: identity`.

---

## Studio shell layout

`App.tsx` renders five regions, all driven by Zustand selectors:

```
┌──────────────────────────────────────────────────────────────────┐
│ LeftNav │ Topbar                                                 │
│         ├────────────────────────────────────────────────────────┤
│         │ NodePanel │ WorkflowCanvas / CodeEditor │ Activity │ RightPanel │
│         ├────────────────────────────────────────────────────────┤
│         │ BottomOutputPanel (when rightPanelMode === 'output')   │
└──────────────────────────────────────────────────────────────────┘
```

| Region | Store(s) | Notes |
|--------|----------|-------|
| LeftNav | `studioSectionStore`, `authStore` | Opens library drawers; workflow drawer |
| Topbar | `workflowStore` | Run, save, validate, dirty indicator |
| NodePanel | `nodeRegistryStore` | Palette; ⌘K focuses search |
| Canvas / Code | `workflowStore` | Lazy-loaded chunks |
| ActivityRail | `workflowStore.uiSlice` | Toggles right panel mode |
| RightPanel | `workflowStore` | Config / run log / copilot; Copilot lazy |
| Bottom output | `workflowStore` | Human-readable + raw JSON output |
| Section drawers | TanStack Query | Fetch when drawer `open` |

**Compact layout** (`useCompactStudio`, `<1024px`): node palette becomes overlay; right panel becomes fixed sheet. CSS class `studio-compact` on root.

**Error boundaries** wrap: node palette, canvas, right panel, bottom output. Topbar, LeftNav, and Copilot inherit parent boundary or handle errors locally.

---

## State management

### Zustand stores

| Store | Responsibility |
|-------|----------------|
| `useWorkflowStore` | Composed editor state — see slices below |
| `useAuthStore` | Cookie session, demo auth, user profile |
| `useThemeStore` | Light/dark + theme variant (Linear / Arc / Cursor) |
| `useToastStore` | Global notification queue |
| `useNodeRegistryStore` | Live node manifest from `GET /node-manifest` |
| `useStudioSectionStore` | Which left-nav library drawer is open |

### Workflow store slices

`workflowStore.ts` is a thin composer — **do not add logic here**. Add to the appropriate slice:

| Slice | File | Holds |
|-------|------|-------|
| Workflow | `workflowSlice.ts` | DAG (nodes, edges), selection, undo/redo, load/save actions |
| Run | `runStream.ts` | SSE event queue, run status, results, validation issues |
| Copilot | `copilotSlice.ts` | Messages, generation timeline, undo checkpoints |
| UI | `uiSlice.ts` | `rightPanelMode`, pane sizes, `workspaceView`, mobile palette |

**Convention:** Components read via selectors (`useWorkflowStore(s => s.workflow)`) and call slice actions — never mutate state directly.

### What stays outside TanStack Query

These are **intentionally imperative** (streaming, autosave, or high-frequency local edits):

- Workflow load/save, draft autosave (`useDraftAutosave`)
- Run execution (`api.runWorkflowStream` → `runStream` slice)
- Copilot SSE generation and chat streaming
- Validation (`POST /validate`)
- Node manifest polling (`nodeRegistryStore` — 15s interval + visibility refresh)

---

## Data layer

### API client (`services/api.ts`)

Single module for REST and SSE:

- `request()` / `fetchJson()` — JSON with cookie credentials
- `ValidationError` — structured validation responses
- SSE parsers for run and copilot streams
- All backend paths under `/api/…`

**Import rule:** Feature code should call `api.*`, not raw `fetch`, except:
- Auth bootstrap (`authStore`, `LoginPage`, `AuthCallback`) — historical; could migrate later
- `DocsPage` — standalone docs fetch
- `nodeRegistryStore` — manifest refresh (parallel to `api.ts` today)

### TanStack Query (`hooks/useLibraryQueries.ts`)

Used for **read-mostly library data** fetched when drawers open:

| Hook | Endpoint | Used by |
|------|----------|---------|
| `useLibrarySkills` | `/skills` | SkillsDrawer |
| `useDataSources` | `/data-sources` | DataSourcesDrawer |
| `useRunLogs` | `/run-logs` | RunHistoryDrawer |
| `useWorkflowsList` | `/workflows` | AutomationsDrawer, WorkflowDrawer |
| `useDraftsList` | `/drafts` | WorkflowDrawer |
| `useAutomations` | `/automations` | AutomationsDrawer |
| `useCopilotChats` | `/copilot/chats` | Copilot |
| … | … | … |

**Pattern:** Pass `open: boolean` → `enabled: open` so queries only run when the drawer is visible.

Cache keys live in `hooks/queryKeys.ts` — always add new keys there.

**Mutations** invalidate related keys in `onSuccess` (e.g. delete workflow → invalidate `queryKeys.workflows`).

---

## Cross-cutting patterns

### Authentication

```
LoginPage / AuthCallback
    → POST /api/auth/* (cookie set)
    → authStore.checkSession() via GET /api/auth/me
ProtectedRoute
    → redirects to /login if unauthenticated
    → skips /me when URL hash contains session_id= (OAuth callback)
```

Demo mode: `lib/env.ts` → `DEMO_AUTH` enables one-click demo login.

### Toasts

```ts
import { toast } from '../store/toastStore'

toast.success('Saved')
toast.error(`Failed: ${err.message}`)
toast.info('Coming soon')
```

Mounted once in `App.tsx` via `<ToastHost />`. Replaces all `alert()` and most silent `console.error` in user-facing paths.

### Error boundaries

- App-level: `main.tsx`
- Regional: `App.tsx` (palette, canvas, right panel, output)
- Logs once via `console.error` in `componentDidCatch` — intentional

Drawer query errors use shared `PanelError` from `components/drawers/shared.tsx`.

### Lazy loading & code splitting

| Chunk | Loaded from |
|-------|-------------|
| `DocsPage` | `main.tsx` |
| `WorkflowCanvas` | `App.tsx` |
| `WorkflowCodeEditor` | `App.tsx` |
| `Copilot` | `RightPanel/index.tsx` |

Vite `manualChunks`: `reactflow`, `monaco` vendor bundles.

**Important:** Import `PALETTE_DND_MIME` from `WorkflowCanvas/constants.ts`, not the lazy `WorkflowCanvas` barrel, to avoid pulling React Flow into the main chunk.

### Accessibility

- `Modal` + `useFocusTrap` — Escape to close, focus cycle
- `aria-pressed` on ActivityRail toggles
- `aria-current` on LeftNav active items
- Section drawers trap focus via `SectionDrawer`

### Theming

Three visual themes via `data-theme` on `<html>`:

| Theme | CSS file |
|-------|----------|
| Linear (default) | `styles/linear-tokens.css` |
| Arc | `styles/arc-tokens.css` |
| Cursor | `styles/cursor-tokens.css` |

Semantic aliases (`--bg-0`, `--text-0`, `--accent`) mapped in `globals.css`.

---

## Data flows

### Edit node config

```
ConfigView field change
    → workflowStore.updateNode(id, config)
    → Canvas + validation badges re-render
    → (debounced) POST /validate
    → runStream slice stores ValidationIssue[]
    → CustomNode badges + ConfigView field highlights
```

### Run workflow

```
Topbar / canvas Run (SaveBeforeRunDialog if dirty)
    → api.runWorkflowStream(workflow)
    → runStream processes SSE:
        node_start      → node status "running"
        node_complete   → store output, status "done"
        node_error      → status "error"
        workflow_complete → finalize run log
    → setRightPanelMode('output')
    → BottomOutputPanel → HumanReadableOutput + collapsible raw JSON
```

### Copilot generate

```
User prompt in Copilot
    → api.streamCopilotGenerate (SSE)
    → timeline phases rendered in Copilot/
    → on complete: workflowStore.setWorkflow(generated)
    → optional undo checkpoint in copilotSlice
    → Canvas renders new DAG
```

### Open library drawer

```
LeftNav click (e.g. "Skills")
    → studioSectionStore.setSection('skills')
    → SkillsDrawer open={section === 'skills'}
    → useLibrarySkills(open) enabled
    → PanelLoading → data or PanelError
```

---

## Testing

| Layer | Command | Coverage |
|-------|---------|----------|
| Unit | `npm test` | Utils: paneUtils, workflowHelpers, copilotUtils, outputFormatUtils, configValidationUtils |
| Typecheck | `npm run typecheck` | Full `tsc --noEmit` |
| Build | `npm run build` | Production bundle |
| E2E | `npm run test:e2e` | Login page, unauthenticated redirect |

E2E config auto-starts Vite on port 3000. Authenticated studio flows are not yet covered.

---

## Conventions for contributors

### Imports

- Prefer **relative imports** today (path aliases `@/`, `@store`, etc. are configured but unused).
- Node metadata: import from `nodes/index.ts`, not `nodes/generated.ts` directly (ConfigView is a known exception).
- Drawer barrel: `from './components/drawers'` — not `SectionDrawers.tsx`.

### Adding a library drawer API hook

1. Add key to `hooks/queryKeys.ts`
2. Add hook + mutation to `hooks/useLibraryQueries.ts`
3. Use `enabled: open` in drawer component
4. Surface errors with `PanelError`, successes with `toast`

### Adding workflow store state

1. Extend `store/workflow/types.ts`
2. Implement in the correct slice file
3. Export types from `workflowStore.ts` if public

### Generated artifacts

After backend node YAML changes:

```bash
python backend/scripts/gen_artifacts.py
```

Regenerates `frontend/src/nodes/generated.ts` — do not hand-edit.

---

## Known debt (not blocking)

| Item | Location | Action |
|------|----------|--------|
| Unused shadcn UI tree | `components/ui/*.jsx` (~46 files) | Delete — zero imports |
| Legacy barrel | `components/SectionDrawers.tsx` | Delete — superseded by `drawers/index.ts` |
| Legacy hook | `hooks/use-toast.js` | Delete — replaced by `toastStore` |
| Unused path aliases | `tsconfig.json`, `vite.config.ts` | Adopt in imports or remove |
| Large monoliths | Topbar, AutomationsDrawer, ConfigView, Copilot, LeftNav | Split when touching |
| Duplicate data-source fetch | `ConfigView` raw fetch vs `useDataSources` | Consolidate to Query |
| Settings placeholder | `LeftNav` toast only | Real settings UI TBD |
| `queryKeys.nodeManifest` | Defined but manifest uses Zustand | Migrate or remove key |

---

## Related docs

- [Architecture overview](./architecture.md) — full system (frontend + backend)
- [Engineering onboarding](./engineering-onboarding.md) — local setup
- [Node catalogue](./node-catalogue.md) — workflow node reference
- [frontend/README.md](../frontend/README.md) — scripts and dev commands
