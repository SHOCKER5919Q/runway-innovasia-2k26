---
version: 1
name: RUNWAY-design-system
base: linear.app
description: "RUNWAY's design language. Linear's structure — a near-black canvas, a four-step surface ladder, hairline borders instead of shadows, one chromatic accent used scarcely, aggressively negative display tracking, and real product UI as the protagonist of every section — with the accent moved from Linear's lavender-blue to a lime-chartreuse, and a small, strictly semantic colour set added because a financial product must distinguish gain from loss. Derived from the Linear analysis in VoltAgent/awesome-design-md (MIT). Design language only: no Linear mark, copy or asset is reproduced."

colors:
  # Brand and interaction. Never means "good".
  primary: "#C6F54A"
  on-primary: "#0D1A10"
  primary-hover: "#D4FA6E"
  primary-focus: "#B3E634"
  primary-soft: "rgba(198, 245, 74, 0.13)"

  ink: "#F4F8F5"
  ink-muted: "#CBD6CE"
  ink-subtle: "#8A978E"
  ink-tertiary: "#64706A"

  # Four-step surface ladder. Hierarchy comes from these, not from shadow.
  canvas: "#06100B"
  surface-1: "#0F1613"
  surface-2: "#141D19"
  surface-3: "#19241F"
  surface-4: "#1D2A24"

  hairline: "#1E2A24"
  hairline-strong: "#2B3A32"
  hairline-tertiary: "#3A4C42"

  # Semantic only. Never a background, never decoration, always paired
  # with a glyph or a sign so colour is never the sole channel.
  semantic-gain: "#34E7B0"
  semantic-loss: "#FF6B7A"
  semantic-warn: "#F5C45E"
  semantic-info: "#6FC8F5"

  # The three states. Three hue families AND three line treatments.
  state-actual: "#6FC8F5"
  state-predicted: "#C6F54A"
  state-simulated: "#F5C45E"

typography:
  display-xl: { fontFamily: Sora, fontSize: 80px, fontWeight: 600, lineHeight: 1.04, letterSpacing: -3.0px }
  display-lg: { fontFamily: Sora, fontSize: 56px, fontWeight: 600, lineHeight: 1.08, letterSpacing: -1.8px }
  display-md: { fontFamily: Sora, fontSize: 40px, fontWeight: 600, lineHeight: 1.14, letterSpacing: -1.0px }
  headline:   { fontFamily: Sora, fontSize: 28px, fontWeight: 600, lineHeight: 1.20, letterSpacing: -0.6px }
  card-title: { fontFamily: Sora, fontSize: 20px, fontWeight: 600, lineHeight: 1.25, letterSpacing: -0.4px }
  body-lg:    { fontFamily: Inter, fontSize: 17px, fontWeight: 400, lineHeight: 1.55, letterSpacing: -0.1px }
  body:       { fontFamily: Inter, fontSize: 15px, fontWeight: 400, lineHeight: 1.55 }
  small:      { fontFamily: Inter, fontSize: 13px, fontWeight: 400, lineHeight: 1.5 }
  label:      { fontFamily: Inter, fontSize: 11px, fontWeight: 600, lineHeight: 1.2, letterSpacing: 0.18em, textTransform: uppercase }
  numeric:    { fontFamily: Inter, fontVariantNumeric: tabular-nums }
  mono:       { fontFamily: JetBrains Mono, fontSize: 12px, fontWeight: 400 }

rounded:
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  xxl: 24px
  pill: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 96px
---

## Overview

The canvas is `#06100B` — near-black with a faint green cast, the same move Linear
makes with blue. On top sits a four-step surface ladder for cards, panels and lifted
tiles, with hairline borders rather than drop shadows. Light text carries everything.

The single chromatic accent is **lime-chartreuse `#C6F54A`**, used on the brand mark,
the primary CTA and the focus ring. Nowhere else.

The page rhythm is **real product UI**. RUNWAY has twenty-one working screens; the
marketing chrome exists to frame them, not to compete with them.

**Key characteristics**

- Dark-canvas system. `#06100B` is the anchor; `#000000` is never used.
- One chromatic accent, used scarcely.
- A four-step surface ladder carries hierarchy without shadow.
- Display tracking pulls hard negative (−3.0px at 80px); body holds near 0.
- Cards are 12px with a 1px hairline. Product panels are 16px.
- No atmospheric gradients and no spotlight cards **inside the application**.

## Two deliberate deviations from Linear

**1 · The accent is lime, not lavender.** Linear's `#5e6ad2` is a lavender-blue. It is
wrong here for three reasons: the brief's references are green-on-black throughout;
green is the convention a financial audience already reads; and violet is explicitly
ruled out for a page's own design by the house frontend rules. Linear's *discipline*
about the accent is kept exactly — one hue, used on brand, CTA and focus only.

**2 · A semantic set exists.** Linear says "don't introduce a second chromatic accent."
A product that reports money cannot honour that literally: gain, loss and warning must
be separable at a glance. So four semantic hues exist under a hard constraint:

> A semantic colour may only carry financial meaning. It is never a background, never
> a decoration, never a brand surface, and it always appears with a glyph or a sign, so
> colour is never the only channel. `gain` sits at hue 168 against the accent's 128 —
> far enough apart that a primary button and a healthy metric never read alike.

## Colours

| Role | Token | Rule |
|---|---|---|
| Brand, CTA, focus | `primary` `#C6F54A` | Interaction only. Never means "good". |
| Canvas | `canvas` `#06100B` | The anchor. Never `#000`. |
| Cards | `surface-1` `#0F1613` | Default lift. |
| Lifted / hover | `surface-2` `#141D19` | Hovered and featured cards. |
| Menus | `surface-3` `#19241F` | Dropdowns, popovers. |
| Borders | `hairline` `#1E2A24` | 1px. Carries depth in place of shadow. |
| Gain | `semantic-gain` `#34E7B0` | Semantic only, with a glyph. |
| Loss | `semantic-loss` `#FF6B7A` | Semantic only, with a glyph. |
| Warning | `semantic-warn` `#F5C45E` | Semantic only. |

The three states each take a hue **and** a line treatment: actual is solid cyan,
predicted is lime with an uncertainty band, simulated is dashed amber. Printed in
greyscale, or seen by someone with deuteranopia, the three stay distinguishable.

## Typography

Display is **Sora** at 600, tracking from −3.0px at 80px to −0.4px at 20px. Body is
**Inter** at 400. Technical strings — invoice numbers, references, ledger fingerprints
— are **JetBrains Mono**.

`font-variant-numeric: tabular-nums` applies to every element that can show a changing
number. Without it a refresh makes the layout twitch, which reads as instability in a
product whose job is to look trustworthy.

Display never exceeds 600. Headings are sentence case, never all-caps; the only
uppercase is the `label` style at 11px with wide tracking.

## Layout

- Base unit 4px; section rhythm 96px.
- Max content width 1280px (1600px for dense application tables).
- Card grids 3-up desktop, 2-up tablet, 1-up mobile.
- Product panels span the full content width. They are the protagonist.
- The dark canvas *is* the whitespace. Sections separate by lifting onto a surface,
  not by gaps.

## Elevation

| Level | Treatment | Use |
|---|---|---|
| 0 | No border, no shadow | Body type, hero text, footer |
| 1 | `surface-1` + 1px `hairline` | Default cards, product panels |
| 2 | `surface-2` + 1px `hairline-strong` | Hovered and featured cards |
| 3 | `surface-3` | Dropdowns, popovers, command palette |
| 4 | 2px `primary-focus` outline | Focus |

Depth is the surface ladder plus hairlines. Drop shadows are resisted almost entirely;
a faint top-edge highlight on a lifted panel is the one exception.

## Shapes

4px chips · 6px tags · 8px buttons and inputs · 12px cards · 16px product panels ·
pill for status only. Buttons are 8px — never pill-rounded.

## Marketing surface

The landing page may use what the application may not: a WebGL hero, scroll-linked
storytelling, an aurora wash, a grid with light beams. These are confined to the
marketing route. Inside the application the rule is Linear's — flat surfaces, hairlines,
and the product doing the talking.

One further constraint, specific to this product: **never animate a live financial
figure.** An animating balance is unreadable at exactly the moment it matters. Counters
exist, and they run on the landing page's static statistics only.

## Do's and Don'ts

### Do
- Keep `canvas` as the anchor. The green cast is intentional.
- Use `primary` only for brand mark, primary CTA, focus ring and link emphasis.
- Use the surface ladder for hierarchy; do not skip levels.
- Pair display 600 with body 400.
- Apply negative tracking aggressively on display.
- Let real product UI be the protagonist of every marketing section.
- Pair every semantic colour with a glyph or a sign.

### Don't
- Don't ship a light-mode marketing page. (The *application* has a light theme; the
  marketing surface does not.)
- Don't use lime as a section background or card fill.
- Don't use a semantic colour decoratively.
- Don't introduce violet or lavender anywhere in the page's own design.
- Don't use atmospheric gradients or spotlight cards inside the application.
- Don't pill-round a button.
- Don't use `#000000` as the canvas.
- Don't promote display type past weight 600.

## Attribution

Structure adapted from the Linear analysis in
[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (MIT),
an inspired-by analysis of design language. No Linear trademark, logo, copy or asset
is reproduced, and this is not intended to pass as Linear's work.
