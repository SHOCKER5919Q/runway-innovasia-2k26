---
version: 3
name: RUNWAY-Grove
base: the user's Google Drive `redesign-fintech-app-ui` reference
description: "RUNWAY's design language after the 2026-11-13 follow-up. Warm paper, deep ink, forest green, one lime accent, Plus Jakarta Sans with Instrument Serif italics, pill buttons, 20px white cards and quiet hairline tables — applied in place to the landing page, sign-in, app shell and all 21 authenticated screens. Light is the default; dark is a companion. Three-state semantics, provenance, accessibility and honesty rules are unchanged. Research: docs/DESIGN_RESEARCH.md. Reference analysis: docs/DRIVE_REFERENCE.md."
supersedes: RUNWAY-Atelier v2 (editorial ivory + ink / electric chartreuse)
---

# RUNWAY / Grove

## Overview

RUNWAY is a financial intelligence layer for Indian MSMEs. It reports money, so
the interface has one job: make reality, expectation and possibility impossible
to confuse while staying calm enough to read at 7 a.m. before a payment run.

The **v3 visual source of truth is the user's Google Drive reference**
(`redesign-fintech-app-ui`). The `runway_ui` tile the user shared is an empty
folder; the project beside it contains the full Next.js UI. Its design language
is now applied **everywhere**: marketing, sign-in, app shell, shared report and
all 21 authenticated screens. The user explicitly chose “Apply it everywhere”
over a blend or app-only change.

What survives from Atelier v2: warm paper, deep ink, real product UI as the
protagonist, one restrained accent, hairlines over shadows, tabular numerals,
and the three-state/provenance/accessibility contracts. What changes: forest
green replaces olive as the primary, the reference lime replaces electric
chartreuse, Plus Jakarta Sans replaces Inter/Sora, the ink rail becomes a paper
rail with forest active states, and the component vocabulary becomes pills,
20px cards, `.tbl` tables and `.field` inputs.

## Palette

| Role | Value | Rule |
|---|---|---|
| Paper canvas | `#f6f4ee` | Warm off-white. Never pure white for the page. |
| Paper 2 | `#efece3` | Subtle inset surfaces, table row hover. |
| Card | `#ffffff` | The only true white. 20px radius, 1px `--line` border. |
| Ink | `#10201a` | All primary type. |
| Ink 2 / 3 | `#46544d` / `#7b8780` | Secondary copy / labels and ticks. |
| Line / Line 2 | `#e6e2d7` / `#d6d1c3` | Hairlines; line 2 for input borders. |
| Forest | `#0c3b2a` | Primary buttons, active nav, inverse story panels, brand tile. |
| Forest 2 / 3 | `#14563d` / `#1d6f50` | Hover, eyebrow, chart series. |
| Lime | `#d3f26b` | The one accent: CTA fills, active icons, brand arrow, selection. |
| Lime 2 | `#bfe24a` | Lime hover. |
| Sage | `#e7eee1` | Quiet tinted panels, demo-account card, icon tiles. |
| Gain / Loss / Warn / Sky | `#0f8a5f` / `#c93b2b` / `#b7791f` / `#2f6da8` | Financial meaning only, never decoration. |

Semantic colours are always paired with a word or glyph. The three states are
separated by **hue AND line treatment**: Actual = blue solid line, Predicted =
forest line with a P10–P90 band, Simulated = amber dashed line. Colour is never
the only channel.

## Typography

- **Plus Jakarta Sans** for everything: 400/500/600/700/800. Display headings
  are 600, `letter-spacing: -0.035em`, `line-height: 1.04`, `text-wrap: balance`.
  All three families are self-hosted in `frontend/public/fonts/` (fontsource
  woff2), matching the Drive reference without a third-party font request.
- **Instrument Serif italic** is reserved for one emphasised word inside a
  display headline (`<em>`, `.serif-i`, `.display em`).
- **JetBrains Mono** for fingerprints, seeds, keyboard hints and the tiny
  provenance metadata only.
- `font-feature-settings: 'cv11', 'ss01'`; all numbers use tabular figures via
  `.num` / `.tnum`.

## Component vocabulary

Defined in `frontend/app/globals.css`, matching the reference file of the same
name:

| Class | Purpose |
|---|---|
| `.card` / `.card-flat` | 20px / 14px white card with a 1px hairline. |
| `.btn`, `.btn-primary`, `.btn-lime`, `.btn-ghost`, `.btn-sm` | 44px pill buttons; forest, lime, outline. |
| `.pill`, `.pill-gain/loss/warn/sky` | Rounded status pills. |
| `.tbl` | Quiet data table: 12px uppercase-ish headers, 14px rows, hover tint. |
| `.field` / `.label` | 46px rounded inputs. |
| `.display`, `.serif-i`, `.eyebrow`, `.num` | Headline, italic accent, 12px forest eyebrow, tabular numbers. |
| `.dots`, `.grain`, `.rise`, `.float`, `.marquee`, `.no-print` | Marketing texture and reduced-motion-aware animation. |

Compatibility aliases (`.rw-card`, `.rw-chip`, `.atelier-*`, `.font-editorial`)
map the existing 21 screens onto the same vocabulary without a per-page rewrite.
`.font-editorial` is now the tight sans display; its `<em>` children remain
serif italic. `.rw-sidebar` is the forest inverse scope used by story panels,
not the app rail.

## Layout

- **Marketing**: sticky 72px paper header, centred hero with a lime “New” pill,
  `display` headline with a serif italic word, two pill CTAs, then a real
  product frame (`CashBandChart`, `Stat`, `StateBadge`, `Evidence`). Marquee,
  idea cards, forest proof panels, FAQ and a full-width lime closing CTA.
- **Sign-in**: paper form on the left (`.field`, forest `.btn-primary`, sage demo
  card), forest dotted story panel on the right with a lime mini-chart.
- **App shell**: 264px paper rail, white business switcher, uppercase group
  labels, forest active nav with lime icons, sticky paper header with a
  rounded-full search, as-of pill, theme toggle and “Ask a question” forest
  button. Main content is centred at 1180px.
- **App pages**: `PageHeader`-style section headings, `card` panels, four KPI
  tiles, charts, hairline lists and a data-quality footer. 21 routes inherit
  the shell and primitives.
- **Shared passport**: the same cards, forced to white for print, with all
  chrome removed.

## Themes, motion and accessibility

- Light is the default; `data-theme="dark"` is an explicit companion with the
  same forest/lime identity on a deep green-black canvas. The boot script sets
  it before first paint.
- Motion is entrance reveals, a marquee, one floating note and an interactive
  lever. Every animation is disabled under `prefers-reduced-motion`. The v1
  WebGL hero, intro curtain, chapter rail and tilt/magnetic primitives were
  deleted in v3 — no route can render a dark 3D glass panel.
- Focus rings use forest-3 at 2px/2px. Contrast on paper is ≥4.5:1 for body
  copy. Charts carry `role="img"`, aria labels, tooltips with full grouped
  rupees and a labelled safety-buffer reference line.
- Print forces a white paper ladder and hides navigation, noise and route bars.

## Product invariants (unchanged)

- Actual, predicted and simulated are stored, versioned and labelled separately.
- A funding-gap answer is shown when asked; forecasts carry sample size, seed,
  horizon and conformal coverage.
- The Copilot refuses unmeasured or unsourced questions and shows its evidence.
- RUNWAY never moves money, never promises loan approval, never claims an
  unmeasured accuracy, never treats health as a credit score and never sells
  data. Simulations are structurally isolated from the ledger.
- No invented testimonials, pricing claims or stock photography. All demo
  figures come from the synthetic seeded ledger.

## Implementation map

| Concern | File |
|---|---|
| Tokens, reference classes, aliases, print/motion | `frontend/app/globals.css` |
| Fonts, metadata, theme boot | `frontend/app/layout.tsx` |
| Brand mark | `frontend/components/runway/brand.tsx`, `frontend/public/favicon.svg` |
| Marketing surface | `frontend/components/runway/atelier.tsx` |
| Real product frame | `frontend/components/runway/product-preview.tsx` |
| App shell, command palette, business switcher | `frontend/components/runway/shell.tsx` |
| Shared primitives (Stat, Panel, SectionHeader, badges, states) | `frontend/components/runway/primitives.tsx` |
| Charts and three-state line treatments | `frontend/components/runway/charts.tsx` |
| Dashboard | `frontend/app/app/page.tsx` |
| Sign-in | `frontend/app/login/page.tsx` |
| 20 other authenticated screens | `frontend/app/app/*/page.tsx` |
| Shared passport | `frontend/app/shared/[token]/page.tsx` |
| Reference analysis | `docs/DRIVE_REFERENCE.md` |
| Earlier research (historical) | `docs/DESIGN_RESEARCH.md`, `docs/REFERENCE_ANALYSIS.md` |
