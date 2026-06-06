---
name: dbsherpa-design
description: Use this skill to generate well-branded interfaces and assets for dbSherpa Studio (Sherpa Studio), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping. dbSherpa Studio is a visual AI workflow-automation studio (DAG editor + Gemini agents + MCP + the "sherpa" copilot).
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Fast orientation
- `README.md` — product context, content fundamentals, visual foundations, iconography, manifest.
- `colors_and_type.css` — **link this first.** All tokens for the three themes
  (`data-theme="dark|light|aurora"`) + semantic type classes. Inter is the only
  product font; Newsreader italic is the aurora display accent (a substitution).
- `assets/` — brand logos (dS monogram, dark + light PNG).
- `preview/` — design-system specimen cards.
- `ui_kits/studio/` — interactive dashboard recreation; lift components + the
  aurora backdrop from `kit.css` / `components.jsx`.

## Non-negotiables
- One cyan/teal accent on a strict neutral ramp; color is **semantic** (status +
  node port types), never decorative. No emoji.
- Inter, tight tracking (−0.01 to −0.04em), dense UI sizes, tabular numerals for metrics.
- Lucide icons (link from CDN), outline, stroke 1.75. Use the dS monogram for brand.
- Cards: 20px radius, hairline translucent borders, soft two-part shadow. Quiet
  motion (140–180ms ease-out, no bounce).
- Three themes share one token contract — build against the variables, never hard-code
  a theme's hex, so a screen works in dark, light, and aurora.

## Rendering note
Local `<script src>` / `<link>` subresources may not resolve in sandboxed preview
frames. For standalone HTML deliverables, inline CSS/JS (see how `ui_kits/studio/index.html`
is built). Glass/`backdrop-filter` over a gradient renders correctly in real browsers
even when html-to-image screenshots drop it — verify in a real browser tab.
