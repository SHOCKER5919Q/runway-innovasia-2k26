# Google Drive UI reference — analysis and application

**Date:** 2026-11-13
**User request:** “nice but can u make it more better like i want u to get this ui
for the pages too check this from my drive”
**Decision (asked and confirmed):** **Apply it everywhere** — replace the Atelier
v2 look on the landing page, sign-in, app shell and all 21 authenticated screens
with the Drive project's forest/lime/pill/card system. A blend or app-only
change was explicitly not chosen.

## What was actually in Drive

The attached screenshot (`/tmp/arena-coding-uploads/image-1.png`) showed only a
Drive folder tile named **`runway_ui`**. That folder
(`14ERuZKZF6d5FissijhxHWZXaNB6gQEEY`, owner Mohammed Salahuddin /
`salahuddinmohammed475@gmail.com`, modified `2026-11-13T02:12:04Z`) is **empty**:
`list_files` with `corpora: "user"`, `corpora: "allDrives"` and a parent query
all returned 0 files.

The UI itself is in the sibling project folder
**`redesign-fintech-app-ui`**
(`1NB5zRlj6HJwPTMmYg05jXs-3uS93DW06`, modified `2026-11-13T02:12:33Z`), which
contains a complete Next.js 16 / React 19 / Tailwind 4 source tree. It was found
by searching all recently modified Drive items and walking the parent ids, not
by guessing from the folder name.

Files read from that project:

| Path (in Drive) | What it told us |
|---|---|
| `package.json` | Next `16.4.2`, React `19.2.6`, Tailwind `4.1.17`, `@fontsource-variable/plus-jakarta-sans`, `@fontsource/instrument-serif`, `lucide-react`, `clsx`, Drizzle/pg. No 3D, no chart library, no animation framework. |
| `src/app/globals.css` | The complete token set and component vocabulary (below). |
| `src/components/ui.tsx` | `Logo`, `Card`, `CardHead`, `PageHeader`, `Stat`, `Pill`, `ButtonLink`, `Empty`, `Tabs`. |
| `src/components/site/header.tsx` | Sticky 72px paper nav, rounded-full links, forest primary button. |
| `src/components/site/hero-mock.tsx` | Browser-chrome product frame: forecast chart + three side stats + two floating notes. |
| `src/components/site/login-form.tsx`, `src/app/login/page.tsx` | Paper form with `.field`/`.label`, forest full-width button, sage demo-account card, forest image/quote panel. |
| `src/components/app/shell.tsx` | 264px **paper** sidebar, grouped nav, forest active item with lime icon, white business card, sticky paper header, 1180px main. |
| `src/app/app/page.tsx` | Greeting + plain-language summary, four KPI cards, forecast chart, health ring, alerts, recommendations, flows, coming-up list. |
| `src/app/(site)/page.tsx` | Centred hero with lime “New” pill, serif-italic emphasised word, two pill CTAs, real product mock, source marquee, idea cards, sage story panel, forest numbers panel, how-it-works, what-if teaser, FAQ, lime closing CTA. |
| `src/components/charts.tsx` | Hand-drawn SVG forecast: forest line, sage band, red dashed buffer, amber dashed scenario. |
| `src/components/app/insights.tsx` | Hairline alert/recommendation lists, pill actions. |
| `src/app/app/layout.tsx`, `src/app/(site)/layout.tsx` | Route-group wrappers. |

The reference source was downloaded only to a temporary workspace folder for
reading; none of its files, images or invented marketing claims are shipped in
RUNWAY. Notably, the reference contains a testimonial, a ₹1,499/month price and
stock photographs. Those were **not** copied: RUNWAY's honesty rules forbid
invented testimonials, unmeasured claims and decorative stock imagery in place
of real product UI.

## The reference design system, verbatim where it matters

```css
--font-sans:  "Plus Jakarta Sans Variable", ui-sans-serif, system-ui, sans-serif;
--font-serif: "Instrument Serif", ui-serif, Georgia, serif;

--color-paper: #f6f4ee;   --color-paper-2: #efece3;  --color-card: #ffffff;
--color-ink: #10201a;     --color-ink-2: #46544d;    --color-ink-3: #7b8780;
--color-line: #e6e2d7;    --color-line-2: #d6d1c3;
--color-forest: #0c3b2a;  --color-forest-2: #14563d; --color-forest-3: #1d6f50;
--color-lime: #d3f26b;    --color-lime-2: #bfe24a;   --color-sage: #e7eee1;
--color-gain: #0f8a5f;    --color-loss: #c93b2b;     --color-warn: #b7791f;
--color-sky: #2f6da8;
```

`.card` = white, 1px `--color-line`, **20px** radius. `.btn` = 44px **pill**;
`.btn-primary` forest, `.btn-lime` lime, `.btn-ghost` outline. `.pill` = 999px
status chip with gain/loss/warn/sky variants. `.tbl` = 12px headers, 14px rows,
hairline borders, `#fbfaf6` row hover. `.field` = 46px 12px-radius input.
`.display` = 600 weight, `-0.035em`, `1.04` line-height, with
`.display em` in Instrument Serif italic. `.num` = tabular numerals. `.dots`,
`.grain`, `.rise`, `.float`, `.marquee` provide the restrained motion, all
disabled under `prefers-reduced-motion`.

## How it was reconciled with RUNWAY

The reference is a different product with a different data layer (`@/lib/data`,
`requireUser`, Drizzle). Copying its pages would have broken RUNWAY's real
FastAPI backend, 21-route information architecture, three-state engine,
provenance contracts and 95 frontend tests. Instead we applied its **design
language in place**:

1. `frontend/app/globals.css` was rewritten with the reference palette and the
   full `.card`/`.btn`/`.pill`/`.tbl`/`.field`/`.display` vocabulary, plus
   compatibility aliases (`.rw-card`, `.rw-chip`, `.atelier-*`,
   `.font-editorial`) so every existing screen inherits it without a rewrite.
   `.font-editorial` became the tight sans display; its `<em>` children keep the
   serif italic. `.rw-sidebar` became the forest inverse scope for story panels.
2. `frontend/app/layout.tsx` switched to Plus Jakarta Sans + Instrument Serif
   (JetBrains Mono retained for fingerprints) and forest/paper theme colours.
   The three families are **self-hosted** from the same `@fontsource*` packages
   the reference uses, in `frontend/public/fonts/` with `@font-face` rules in
   `globals.css`; no third-party font request is made at build or in the browser.
3. `frontend/components/runway/brand.tsx` and `favicon.svg` now use the
   reference forest tile with a lime rising-line mark.
4. `frontend/components/runway/shell.tsx` keeps every working control
   (business switcher, command palette, as-of, theme, demo ribbon, 21-route
   context) but adopts the paper rail, forest active nav, white business card,
   rounded-full search and 1180px main.
5. `frontend/components/runway/primitives.tsx` maps `Stat` → reference `Stat`,
   `SectionHeader` → `PageHeader`, `Panel` → `Card`/`CardHead`, and badges →
   `.pill`, while preserving the `title` tooltips, headings, `role="alert"`,
   definition lists and non-colour-only delta wording that the tests enforce.
6. `frontend/app/login/page.tsx`, `frontend/app/app/page.tsx`,
   `frontend/components/runway/atelier.tsx`,
   `frontend/components/runway/product-preview.tsx` and
   `frontend/app/shared/[token]/page.tsx` were restyled to the same vocabulary.
   The landing hero, nav and closing CTA now follow the reference composition;
   the interactive `ProductPreview` still mounts the real shared charts and
   primitives.
7. `frontend/components/runway/charts.tsx` needed no code change: it already
   reads CSS variables, so remapping `--chart-*`, `--state-*` and `--fin-*`
   recolours every chart while keeping solid/band/dashed state encoding.

## Cleanup after the user's follow-up screenshot

The user then attached a screenshot of a **dark tilted 3D glass card with green
bars** and said they could not see the changes and did not like it. That image is
the v1 `hero3d.tsx` WebGL hero (stacked `MeshTransmissionMaterial` panels with
emissive forecast bars), not the Drive reference. It was already unmounted, but a
stale prerendered HTML document could still show it in an old browser tab.

To make that impossible:

- `frontend/components/runway/hero3d.tsx`,
  `frontend/components/runway/hero3d-loader.tsx` and
  `frontend/components/runway/premium.tsx` (`IntroCurtain`, `ChapterRail`) were
  **deleted**. No route can mount WebGL, an intro curtain or a scroll rail now.
- `frontend/app/page.tsx` exports `dynamic = "force-dynamic"` and
  `revalidate = 0`; `frontend/app/layout.tsx` sends no-cache meta tags and a
  `runway-design="grove-v3-drive-reference"` marker. A refresh can no longer
  resurrect the old static document.
- The preview was restarted on a fresh port so the browser gets a new origin
  with no cached HTML.
- `README.md` now records the removal instead of saying those primitives are
  merely “retained but unmounted”.

## What did **not** change

- Actual / predicted / simulated separation, scored forecasts with sample
  sizes, refusals, provenance notes, read-only money handling, health-not-credit
  -score wording, and structurally isolated simulations.
- The 21-route navigation, API contracts, demo credentials
  (`owner@runway.demo` / `demo1234`) and seeded as-of date `2026-11-07`.
- The 95-test frontend suite and the print stylesheet for shared passports.
- No real business, testimonial, pricing claim or accuracy claim was invented.

## Traceability

- `DESIGN.md` v3 (`RUNWAY-Grove`) is the current source of truth.
- `docs/DESIGN_RESEARCH.md` and `docs/REFERENCE_ANALYSIS.md` are historical
  documents for v1/v2 and are explicitly marked as such.
- Temporary Drive downloads (`.drive_refs/`, `google_drive/`) are scratch files
  and are removed before delivery; no reference source is committed.
