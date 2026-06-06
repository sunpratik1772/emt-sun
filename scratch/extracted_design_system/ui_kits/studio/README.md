# Studio — UI Kit

An interactive, high-fidelity recreation of the **dbSherpa Studio dashboard home**
(the "Studio" surface). Open `index.html` and use the theme control (top-right) to
switch **dark / light / aurora** live — every component reads the same token
contract, so the third theme is seamless.

This is a *recreation for prototyping*, not production code: interactions are faked
(toasts stand in for navigation), data is mock. The goal is pixel-faithful chrome
you can lift into new designs.

## Files
| File | What |
|---|---|
| `index.html` | **Self-contained** host — inlines the CSS + components so it renders anywhere (offline, PDF, embeds). Open this. |
| `kit.css` | The 3-theme token contract + all dashboard component styles (editable source). |
| `data.js` | Mock data — user, nav, stats, workflows, run health, suggestions. |
| `components.jsx` | Presentational React components (editable source). |
| `app.jsx` | The shell that composes them + wires interactions (editable source). |

> `index.html` is **generated** by inlining `kit.css` + `data.js` + `components.jsx`
> + `app.jsx`. Edit those source files, then re-inline them into `index.html`
> (the three blocks live at the bottom of the file). They're split out because
> local `<script src>`/`<link>` subresources don't always resolve in sandboxed
> preview frames — inlining guarantees the kit renders everywhere.

## Components covered
- **Rail** — collapsed icon nav (brand monogram, Lucide glyphs, avatar). In aurora
  it's a dark frosted capsule with light icons for contrast over the sky.
- **Header** — time-aware serif eyebrow + Inter greeting, search trigger (⌘K),
  **theme segmented control** (dark/light/aurora), New workflow button.
- **SherpaBar** — the "Ask Sherpa anything…" prompt + circular send + 3 suggestion
  chips (click a chip to load it into the input).
- **StatCard** — glass metric tile with a generated micro-sparkline (recolors to
  accent on hover).
- **HealthCard** — success-rate card with ambient color blobs + engine-status pill.
- **ActivityCalendar** — run-activity heatmap (GitHub-style), heat tones from `--heat`.
- **WorkflowCard** — status-tinted glass card with chips + "Open Studio" action,
  plus the dashed **NewWorkflowCard**.
- **Toast** — transient confirmation for clicks.

## Icons
Lucide via CDN, rendered from `<i data-lucide="…">` and converted by
`lucide.createIcons()` after each React render (stroke 1.75 to match the Arc pack).

## Source of truth
Recreated from `frontend/src/components/dashboard/*`, `pages/DashboardHome.tsx`,
`components/LeftNav.tsx`, and `styles/dashboard.css` in
[sunpratik1772/Sunny-studio](https://github.com/sunpratik1772/Sunny-studio).
The **aurora** theme is a new proposal (not in the product); it reuses the existing
token names so it drops into any screen.
