# Reference analysis

How the supplied design material became RUNWAY's design system.

**The reference files are unmodified.** `Reference/` contains exactly what was
supplied. Nothing in it was edited, moved or overwritten.

---

## What was supplied

| File | What it is |
|---|---|
| `RUNWAY Financial Copilot UI Board.png` | 1536 × 1024. Fifteen annotated screens laid out as a product board — landing, sign-in, sign-up, onboarding, data connection, main dashboard, Business State Centre, predicted state, simulated state, digital twin, AI copilot, recommendations, reports, profile, and a layered architecture diagram. |
| `financial-analytics-dashboard.zip` | A Next.js 16 + React 19 + Tailwind v4 bundle: ~60 shadcn/ui components, a 1,230-line mock analytics dashboard, and an OKLCH token set on a teal-accented obsidian base. |

The two disagree on accent colour — the board is violet, the bundle teal. The board
is RUNWAY-specific and annotated, so **the board is the design authority**; the
bundle contributed its token *structure* and its motion patterns.

---

## Extracting the palette

Sampled from the PNG rather than guessed:

```
page background   #070916      very dark navy-indigo, not neutral black
card surface      #0F1322 – #121626
elevated surface  #141A2B
```

The base is deliberately *blue*-dark, not grey-dark. A neutral charcoal reads as a
developer tool; the indigo cast reads as financial software, and it gives the violet
accent somewhere to sit.

Accents were too sparse in the board to extract by frequency, so they were read from
the annotated elements: a violet primary (buttons, active tabs, the brand mark), a
teal-green for positive movement, a rose for negative, an amber for warning.

### The resulting token set

```css
--background: oklch(0.118 0.028 275);   /* #070916 */
--card:       oklch(0.163 0.027 273);
--primary:    oklch(0.638 0.206 288);   /* violet — interaction only */
--fin-gain:   oklch(0.800 0.165 165);
--fin-loss:   oklch(0.680 0.205 14);
--fin-warn:   oklch(0.812 0.149 77);
```

**OKLCH, not hex or HSL.** In OKLCH the first component is *perceived* lightness, so
`oklch(0.80 0.165 165)` and `oklch(0.68 0.205 14)` are genuinely comparable in
weight. In HSL they would not be — a pure blue at 50% lightness looks far darker
than a pure yellow at the same number, which is why HSL palettes always have one
series visually shouting.

---

## Rules the palette enforces

**Violet is for interaction and the product's own voice. It never means "good".**
The board uses violet for buttons, active states and the brand. If violet also meant
"positive", a primary button and a healthy metric would be indistinguishable at a
glance.

**Gain, loss and warning are the only colours carrying financial meaning**, and each
is always paired with a glyph or a sign. A delta renders as `▲ ₹2,40,000` in teal,
never as teal alone (WCAG 1.4.1).

**Each of the three states has its own hue *and* its own line treatment.** Actual is
solid teal, predicted is violet with an uncertainty band, simulated is dashed amber.
Printed in greyscale, or seen by someone with deuteranopia, the three remain
distinguishable.

---

## Layout

Taken from the board's main dashboard panel:

- **264px sidebar**, collapsible to 72px, grouped by workflow — *Today*, *Look
  ahead*, *Money*, *Standing*, *Assist* — rather than alphabetically. The board's
  ordering (Home, Business State Centre, Digital Twin, Forecasts, Scenarios,
  Recommendations, Copilot, Reports, Integrations) was preserved and the grouping
  added, because eighteen flat items is a list and five groups is a workflow.
- **Four headline tiles** across the top, exactly as the board shows: available
  cash, receivables, payables, runway.
- **A wide forecast chart beside a narrow health panel**, matching the board's
  7:3 split.
- **A three-across lower row**: ageing, obligations, flows.
- **Recommendation cards** as a four-up grid.

The Business State Centre's three-tab layout (Actual / Predicted / Simulated) is
taken directly from the board, with a fourth "compare all three" view added because
the board's own architecture diagram implies the comparison.

---

## Typography

The board's headings are geometric and slightly editorial; its body text is a
standard UI sans.

| | | |
|---|---|---|
| **Sora** | Display — headings, headline figures | Geometric with presence. Gives numerals weight without the generic-SaaS feel of Inter everywhere. |
| **Inter** | Body, UI, tables | Unmatched legibility at 11–14px, which is most of this interface. |
| **JetBrains Mono** | Invoice numbers, references, fingerprints | Clear zero, unambiguous `1Il`. |

`font-variant-numeric: tabular-nums` is applied to every element that can show a
changing number. Without it, a refresh makes the layout twitch — which reads as
instability in a product whose job is to look trustworthy.

---

## What was taken from the zip bundle

**Kept:** the OKLCH token *structure* (`:root` custom properties + Tailwind v4
`@theme inline`), the card shadow stack, the spring and ease-out curves
(`[0.16, 1, 0.3, 1]`), and the Recharts composition patterns.

**Replaced:** the teal accent, with the board's violet.

**Removed:** all ~60 shadcn components and ~25 Radix dependencies. After the screens
were built on hand-written primitives, every one was unused. Shipping an unused
component kit would have added weight and an accessibility surface nobody had
checked.

**Fixed:** the bundle sets `typescript.ignoreBuildErrors: true`. RUNWAY's production
build type-checks and fails on an error.

---

## Where the implementation goes beyond the board

The board is a static layout. These were added because the product needs them:

| Addition | Why |
|---|---|
| **Light theme** | Accountants work in daylight and present on projectors, where a dark theme washes out. One token set, redefined under a selector. |
| **State badges everywhere** | The board shows three tabs; the product needs the distinction on every tile, every chart series and every copilot answer. |
| **Evidence disclosure** | Every alert and recommendation expands to its triggering evidence and its ranking terms. A board cannot show this; a trustworthy product must. |
| **Provenance notes** | Small italic notes under charts and tables explaining how a figure was derived. |
| **Data-quality strip** | Persistent, with the specific warnings. A forecast built on a stale ledger is fiction. |
| **Demo ribbon** | A permanent bar stating that the data is synthetic. Non-negotiable. |
| **Command palette** | ⌘K across eighteen screens. |
| **As-of control** | Point-in-time evaluation is a product feature, not a debug tool. |
| **Reduced-motion handling** | In JavaScript, so it disables Lenis and the GSAP ticker too — not only the CSS. |

---

## Motion

Three principles, applied throughout:

1. **Motion explains, it does not decorate.** The sliding navigation indicator
   (`layoutId`) shows where you went. Expanding evidence panels show where the
   detail came from. Staggered reveals establish reading order. Nothing moves
   without a reason.
2. **Never animate a live financial figure.** An animating balance is unreadable at
   exactly the moment it matters. `CountUp` exists and is used **only** on the
   landing page's static statistics.
3. **Smooth scroll stays on the marketing surface.** Lenis is on the landing page
   only. Hijacking scroll inside a financial table is hostile — people scan tables,
   they do not glide through them.

`prefers-reduced-motion` is honoured in CSS *and* checked in JavaScript before Lenis
or the GSAP ticker start.

---

## Accessibility

- Semantic landmarks; a skip link to the main region.
- `aria-current="page"` on navigation, `aria-expanded` on every disclosure,
  `aria-pressed` on toggles, `role="alert"` on errors, `role="status"` with
  `aria-live` on loading regions.
- Visible `:focus-visible` ring on every interactive element.
- Colour never the only channel: deltas carry a glyph, states carry a line
  treatment, the risk heatmap carries numbers in the cells.
- Charts carry `role="img"` and a descriptive `aria-label` stating what the shape
  shows.
- Every form control has a real `<label>`.
- Body text meets 4.5:1 against its surface; the muted foreground was lightened from
  the bundle's value to reach it.
