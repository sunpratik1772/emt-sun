# dbSherpa Studio — Design System

A working design system for **dbSherpa Studio** (also written *Sherpa Studio*), reconstructed
directly from the product's frontend source so design agents can build on-brand
screens, prototypes, and assets.

---

## What dbSherpa Studio is

dbSherpa Studio is a **visual workflow automation studio**. You build pipelines as a
DAG on a canvas, transform data with **Starlark code** nodes, reason with **Gemini agent**
nodes, and reach out to live systems through **MCP integrations** (Confluence, Jira,
GitHub). The headline feature is **sherpa** — an AI copilot that turns plain-English
requests into validated, runnable workflows.

The product surface is a single-page web app:

- **Studio** — the core workspace: a node palette, a workflow canvas, a config/output
  right panel, and a dashboard "home" with stats, run health, and recent workflows.
- **Sherpa Copilot** — the conversational panel that plans, builds, and auto-fixes
  workflows ("Ask Sherpa anything…").
- **Login / marketing** — a dark auth page tagged *"Agentic workflow studio."*

It ships with **36 nodes**, vetted demo workflows, and a run-history / automations layer.

### The three themes
The product ships **dark** (default) and **light**. This system adds a third —
**aurora** — a painterly warm→cool gradient seen through frosted glass, built to be
**seamless across every screen**: it's just another value of the same token contract
(`[data-theme="aurora"]`), so any component that reads the tokens renders correctly.

---

## Sources

Everything here was lifted from the product's own code. If you have access, read deeper:

| Source | URL |
|---|---|
| Primary repo (attached) | https://github.com/sunpratik1772/Sunny-studio |
| Public mirror | https://github.com/sunpratik1772/sherpa-co-latest |
| Related | https://github.com/sunpratik1772/dbsherpa-studio |

Key files referenced: `frontend/src/styles/linear-tokens.css`, `globals.css`,
`dashboard.css`; `frontend/tailwind.config.js`; the `components/dashboard/*` and
`pages/DashboardHome.tsx`, `LoginPage.tsx`; `components/LeftNav.tsx`. Icons are
**Lucide** (wrapped as the "Arc" pack, stroke `1.75`). Logos live in
`frontend/public/brand/`. **Explore these repos** to build with higher fidelity than
this snapshot captures.

Concept screenshots (in `uploads/`) supplied the aurora direction: a navy→amber→cream
gradient with frosted cards, app-icon tiles, and a serif-italic greeting.

---

## Content fundamentals

How dbSherpa Studio writes.

- **Voice — calm, capable, encouraging.** It's a power tool that stays out of the way,
  then cheers small wins: *"Nice momentum — +2 vs last month."*, *"running on autopilot."*
- **Second person, present tense.** Copy talks to *you* about *your* work:
  *"In your library."*, *"Create your first."*, *"Run a workflow in Studio."*
- **Sentence case everywhere** except **UPPERCASE micro-labels** on stats
  (`WORKFLOWS`, `RUNS THIS MONTH`, `AUTOMATIONS`) with wide letter-spacing.
- **Imperative for actions, short and verb-first:** *Run workflow*, *New workflow*,
  *Open Studio*, *Loop me in*, *Run "Trade Anomaly Detection and Reporting"*.
- **The copilot is lowercase "sherpa."** The app is "dbSherpa Studio" / "Studio."
  The prompt placeholder is always *"Ask Sherpa anything…"* (note the ellipsis char `…`).
- **Time-aware greeting** as the page H1: *"Good morning, Sarah"*, *"Good evening, John."*
- **Ellipsis + em dash** are the punctuation signature: *"Let's build something amazing…"*,
  *"12 runs · 1 failed."* (middot separates run stats).
- **Suggested prompts are concrete and task-shaped**, written as if you typed them:
  *"Create an Excel report from orders.csv with sorted top contributors."*
- **Status copy is plain and honest:** *Engine online / Engine offline*,
  *No runs yet this month*, *Not run yet*, *No streak yet*.
- **No emoji.** Never. Iconography carries all the visual signalling.
- **Numbers are real and tabular** — counts, percentages, deltas (`92%`, `+2`, `3/22`).

---

## Visual foundations

- **Lineage.** The chrome is explicitly *Linear / Railway / Cursor*-inspired:
  high-contrast neutral palette, hairline borders, near-black canvas, restraint over
  decoration. Inter is "the font Linear/Railway/Cursor use."
- **Color.** One cyan/teal accent (`#3eb5db` dark, `#2489ab` light) on a strict
  neutral ramp. Color is used *semantically*, not decoratively — status (success
  green, danger red, warning amber) and **port types** (amber dataframe, sky object,
  green scalar, indigo string-list, pink workflow). Aurora adds a warm pole
  (`--accent-warm` ember `#d9663a`).
- **Type.** Inter only, in the product — sans, headings, and "mono" are all Inter.
  Dense UI sizes (10.5–13.5px) with tight tracking (`-0.01em` to `-0.04em`) and
  `font-feature-settings: 'cv01','ss03'`. Big metrics use tabular numerals at
  32–44px, `-0.04em`. Aurora introduces **Newsreader italic** purely as a display
  accent for greetings (a substitution — see Caveats).
- **Backgrounds.**
  - *Dark*: a faint dot grid (`radial-gradient(circle at 1px 1px …)`, 24px) over a
    `#08090a → #000` vertical wash, masked to a soft ellipse. No animated blobs —
    "Linear ethos."
  - *Light*: flat white, dot grid at 3% opacity.
  - *Aurora*: a layered radial gradient — deep navy top-right, ember bottom-centre,
    cream pocket mid-left — fixed behind everything so all screens share one sky.
- **Surfaces & glass.** Cards are `20px`-radius with soft shadows. The dashboard uses
  **frosted glass** (`backdrop-filter: blur(14–22px) saturate(1.15)`) with a translucent
  fill and a 1px inset highlight in light/aurora. Dark mode keeps blur *off* (opaque
  panels) by design.
- **Borders.** Hairlines made of translucent white/black: `--border-soft` (≈0.08),
  `--border` (≈0.14), `--border-strong` (≈0.20). Never heavy 1px solid neutrals.
- **Shadows / elevation.** Two-part: a subtle inset top highlight + a diffuse drop
  (`0 4px 20px rgba(0,0,0,.2)` dark; `0 8px 24px rgba(0,0,0,.06)` light;
  `0 14px 40px rgba(24,38,60,.18)` aurora). Status cards get a *colored* glow ring.
- **Corner radii.** `6 / 8 / 12` for controls and small surfaces; `14px` for the
  Sherpa prompt bar; `20px` for dashboard cards; `999px` pills and round icon buttons.
- **Motion.** Quiet and quick. `cubic-bezier(0.2,0,0,1)` ease-out at 140–180ms for
  hover/color; a 520ms welcome fade-in (`translateY(6px)→0`); edges animate a dashed
  `stroke-dashoffset` flow when running; spinners blink softly. No bounce, no parallax.
- **Hover states.** Cards lift `translateY(-3px)` and brighten their border; ghost
  buttons fill with `--bg-2`; nav items swap to `--bg-2`/`--bg-3` and brighten text;
  the sherpa send button scales `1.04`; sparklines fade `0.55→1` and recolor to accent.
- **Press / active.** Segmented controls invert (active pill = `--segment-active-bg`,
  near-black in dark, white in light/aurora). Accent buttons darken to `--accent-lo`.
- **Transparency & blur** appear only on the dashboard glass layer and the gradient
  themes — the workflow canvas chrome stays opaque for legibility.
- **Imagery.** The product is essentially image-free; meaning is carried by Lucide
  icons and the node graph. The aurora concept is the one place with painterly color.

---

## Iconography

- **System: Lucide.** Wrapped in-house as the **"Arc" icon pack**
  (`frontend/src/icons/arc.tsx`) with a fixed `strokeWidth = 1.75` and consistent
  sizing (14–16px in UI, 44px tiles). Outline style, rounded joins, no fills.
- **No icon font / sprite** — icons are React components from `lucide-react`. For
  static HTML, this system links Lucide from CDN (`lucide@latest`) and renders by
  `data-lucide` name — a faithful match, not a substitution.
- **Common glyphs** (verbatim from the Arc export): `LayoutGrid` (dashboard),
  `Workflow`, `LayoutTemplate` (templates), `Boxes` (node library), `Lightbulb`
  (skills), `Database` (data sources), `Activity`, `Settings`, `Sparkles` (sherpa /
  AI), `ArrowUpRight` (open / send), `Plus`, `Search`, `Play`, `Zap`, `Bot`,
  `GitBranch`, `Github`, plus status (`CheckCircle2`, `XCircle`, `Loader2`).
- **Brand mark.** A geometric **"dS" monogram** — an `S` fused with a descending
  `d/j` stroke. Theme-aware PNG (`assets/dbsherpa-logo-dark.png` = white mark on near
  black; `assets/dbsherpa-logo-light.png` = ink mark on white). Used at ~24–28px in
  chrome and as the favicon.
- **No emoji, no unicode-as-icon.** The only "unicode as glyph" is the middot `·` as a
  stat separator and `…` in placeholders.

---

## Index — what's in this system

| Path | What |
|---|---|
| `README.md` | This file — context, content + visual foundations, iconography, index |
| `SKILL.md` | Agent-Skills manifest (works in Claude Code) |
| `colors_and_type.css` | **Start here.** All tokens for the 3 themes + semantic type classes |
| `assets/` | Brand logos (dark + light PNG monogram) |
| `preview/` | Design-system cards (typography, color, spacing, components) |
| `ui_kits/studio/` | Interactive recreation of the Studio dashboard (all 3 themes) |

### Quick start for an agent
1. Link `colors_and_type.css` and set `data-theme="dark|light|aurora"` on `<html>`.
2. Add the `.ds-root` class to `<body>` for base font + features + background.
3. Pull components and the aurora backdrop from `ui_kits/studio/`.
4. Link Lucide from CDN for icons; use the `dS` monogram from `assets/` for brand.

---

## Caveats / substitutions

- **Newsreader (serif italic)** is a **substitution**. The product codebase uses only
  Inter; the elegant serif greeting comes from the concept screenshots, whose exact
  face isn't in the repo. Newsreader is the closest free match. Swap it if you have the
  real file.
- **Aurora** is a *new* theme proposed here, not yet in the product — it reuses the
  existing token contract so it drops into every screen, but values may want tuning
  against a real build.
- Logos are **opaque PNGs** (no transparent glyph). On arbitrary colors, place them on
  their matching dark/light chip rather than knocking out the background.
