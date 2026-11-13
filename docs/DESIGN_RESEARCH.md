# Design research — RUNWAY / Atelier

> **Historical document (v2).** On 13 November 2026 the user supplied a Google
> Drive UI reference and chose to **apply it everywhere**. The current system is
> **RUNWAY / Grove v3**, specified in `DESIGN.md` and analysed in
> `docs/DRIVE_REFERENCE.md`. The research below remains the provenance of the
> original in-place redesign and of the product invariants that still hold.

**Date:** 13 November 2026
**Brief:** redesign RUNWAY in place — the landing page, the application shell and
the pages behind it — into an original, research-informed fintech product. The
user supplied three reference templates and asked for additional internet
research rather than a copy of any one of them.

The resulting direction is **editorial ivory + ink**: a warm paper canvas, deep
pine-black typography, one electric chartreuse accent, a deep-ink navigation
rail, and the real product UI as the only illustration.

---

## 1. What the supplied templates taught us

| Reference | What is worth keeping | What we deliberately left behind |
|---|---|---|
| [Plax — Finance & Fintech HTML template](https://preview.themeforest.net/item/plax-finance-fintech-startup-html-template/full_screen_preview/52942901) | A direct hero promise, an above-the-fold CTA, a compact trust strip, and feature sections built around product visuals. | The consumer-card metaphor, stock character illustrations, repeated generic security copy and fake brand walls. RUNWAY is a B2B intelligence layer, not a consumer card. |
| [Synox — Online Banking](https://html.xpressbuddy.com/synox/index_online_banking.html) | A five-part feature rhythm, concrete numbers near the hero, and card/transaction imagery that hints at real screens. | Decorative circles and shadows, duplicated statistics, filler copy, and a logo carousel that says nothing about the product. |
| [Awaiken — Fintech video landing](https://html.awaikenthemes.com/fintech/index-video.html) | An editorial section cadence, numbered services, counters and a calmer consulting tone. | Stock photography, generic "financial strategies" language, pricing tables and process diagrams that belong to a services firm rather than software. |

**Synthesis:** all three templates are visually competent but structurally
interchangeable. They lean on stock imagery, decorative shapes and broad claims.
The strongest signal in each is the moment it shows a real interface. That
became the organising principle of Atelier: *the product is the illustration.*
No template asset, copy string or layout was reproduced.

Visual references consulted during the pass included
[Mercury's landing page](https://www.saasframe.io/examples/mercury-landing-page),
[Ramp-style bento grids](https://reddit.com/r/webdesign/comments/1p2wxce/fintech_landing_page_design)
and [light financial dashboards](https://www.behance.net/search/projects/financial%20dashboard%20ui%20design).
They were studied for rhythm and density, not copied.

---

## 2. What current research says

### The product UI is the trust signal
2026 landing-page reviews repeatedly put real product screenshots above stock
illustration: the strongest pages "show, not tell", with the hero deciding the
visit in three to five seconds [5](https://framiq.app/blog/best-saas-landing-pages-2026).
Mercury and Ramp are cited as the fintech benchmarks precisely because their
screenshots feel native to the design system rather than dropped in afterwards
[2](https://gridrebels.studio/post/20-best-saas-website-designs-in-2026-examples-that-actually-convert).
Ramp in particular formalised the bento grid into a system with uniform gutters
and size-as-hierarchy rules [1](https://toimi.pro/blog/best-saas-website-designs/).

### Trust is architectural, not decorative
A proof-first information architecture puts value, one credibility cue and one
CTA above the fold, explains how the product works in plain steps, and surfaces
security specifics instead of hiding them behind a padlock icon
[1](https://wsa.design/news/top-10-fintech-ux-design-best-practices-for-2026).
Progressive disclosure — summary first, then visual breakdown, then raw data —
is the recommended shape for calm financial dashboards
[1](https://wsa.design/news/top-10-fintech-ux-design-best-practices-for-2026),
[4](https://testpapas.com/blog/fintech-ux-design).
AI-generated statements need a visible source of truth: users must be able to
click a claim and land on the rows behind it, or trust collapses
[2](https://foundey.com/blog/fintech-dashboard-design-2026).
Explainability, override and human escalation are treated as guardrails, not
features [5](https://medium.com/design-bootcamp/ai-ux-in-fintech-a-comprehensive-guide-55f84114c0a0).

### Dark mode is no longer a personality
Dark mode is described as table stakes in 2026; what matters is contrast, one
restrained accent and consistent density
[2](https://foundey.com/blog/fintech-dashboard-design-2026).
A modern dashboard is built from flat surfaces with 1px borders, a 256px
sidebar, four to six KPI cards and a twelve-column content grid
[3](https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/).
That gave us permission to make **light** the default and treat dark as an
explicit companion theme, rather than following the category's default black
canvas.

### Charts should be quieter than the data
Dark-mode guidance — equally useful on paper — says gridlines should recede to
a whisper, concurrent series should be limited, and tooltips should sit on a
slightly elevated surface with instantly legible numbers
[1](https://www.wandr.studio/blog/dark-mode-fintech-dashboard-design).
Semantic reds and greens must be tuned per theme and always paired with a glyph
or sign, because colour alone fails a meaningful share of users
[1](https://www.wandr.studio/blog/dark-mode-fintech-dashboard-design),
[3](https://procreator.design/blog/best-fintech-product-design-tips-growth/).

### Motion has grown up
The era of flashy gradients is giving way to restrained motion, modular
storytelling, authentic product UI and clean typography
[3](https://theqream.com/blog/best-fintech-websites-2026).
Scroll-driven narrative remains effective when it is disciplined
[1](https://toimi.pro/blog/best-saas-website-designs/),
but excessive 3D and animation can distract from financial information
[4](https://usatechtrend.com/fintech-websites-dark-mode-examples-15-stunning-designs-to-inspire-you-in-2026/).
Accessibility guidance asks for at least 4.5:1 contrast, labelled inputs,
keyboard-tested flows and text alternatives for charts
[3](https://procreator.design/blog/best-fintech-product-design-tips-growth/).

---

## 3. What we invented from it

| Research signal | Atelier decision |
|---|---|
| Real product UI is the hero | The landing hero mounts the actual `CashBandChart`, `StateBadge` and stat surfaces against the demo ledger's figures. There is no screenshot and no generated image. |
| Proof-first IA | A trust strip, an explicit "what it will never do" section, visible provenance strings and an FAQ that answers the awkward questions before sign-in. |
| One restrained accent | One chartreuse hue in two lightnesses: deep olive for text, electric `#C9F24F` for fills, marks and the primary CTA. It never means "good". |
| Calm, legible density | Warm ivory paper, a four-step surface ladder, hairline borders, a deep-ink 264px rail, four KPI tiles and a 12-column product frame. |
| Progressive disclosure | Landing: promise → real screen → six capabilities → three states → interactive lever → proof. App: plain-language briefing → KPI strip → forecast → evidence → raw tables. |
| Explainable AI | The decision desk and copilot tiles show the tool, the evidence rows and the deterministic verification line. Every AI claim is checkable. |
| Restrained motion | Entrance reveals, one working lever, one animated path, one marquee. No WebGL, no pinned scrollytelling, no animated live financial figures. `prefers-reduced-motion` disables all of it. |
| Semantic safety | Gain, loss, warning and info are always paired with a glyph or sign; the three states each keep a hue **and** a line treatment — solid, banded, dashed. |
| Both themes | Light is the identity; dark is a complete companion token set, not an afterthought. The deep-ink rail works in both. |
| Editorial typography | `Instrument Serif` for display, `Sora` for UI headings, `Inter` for body, `JetBrains Mono` for references, and tabular numerals on every changing figure. |

---

## 4. Explicitly rejected

- Stock photography, illustrated people, 3D glass panels and aurora-as-brand.
- A dark-gradient hero as the default fintech costume.
- Decorative KPI counters on live balances.
- Fake customer logos, invented testimonials or unmeasured accuracy claims.
- Violet/lavender, multi-hue gradients and semantic colour used as decoration.
- Copying a template's section order, wording or assets.
- Animating a live financial figure: an animating balance is unreadable exactly
  when it matters.

---

## 5. Implementation map

| Surface | File | What changed |
|---|---|---|
| Tokens, themes, utilities | `frontend/app/globals.css` | v2 Atelier token set (now superseded by the Grove v3 token set). Light default, dark companion, scoped ink-rail variables, editorial utilities, reduced-motion and print rules. |
| Fonts, theme boot, metadata | `frontend/app/layout.tsx` | Instrument Serif added; light is the pre-paint default; new favicon and theme colours. |
| Brand mark | `frontend/components/runway/brand.tsx` | New reusable mark that works on paper and on the ink rail through token scoping. |
| Landing | `frontend/components/runway/atelier.tsx`, `frontend/app/page.tsx` | Entirely new editorial page: real product hero, bento instrument, three states, interactive product preview, decision lever, proof, FAQ and closing CTA. |
| Live demo section | `frontend/components/runway/product-preview.tsx` | Restyled to the paper frame; still mounts the app's real charts and primitives. |
| App shell | `frontend/components/runway/shell.tsx` | Deep-ink rail, new top bar, route breadcrumb for every screen, light default theme, restyled command palette. |
| App primitives | `frontend/components/runway/primitives.tsx` | Editorial section headers, paper panels, hairline rules. |
| Dashboard | `frontend/app/app/page.tsx` | New masthead, plain-language briefing with evidence, KPI strip and decision-first layout. |
| Sign-in | `frontend/app/login/page.tsx` | Editorial split: ink promise panel on the left, paper form on the right; demo accounts preserved. |
| Specification | `DESIGN.md` | Was rewritten as the v2 Atelier system; `DESIGN.md` is now the v3 Grove specification. |

---

## 6. Sources

User-supplied templates:

- [Plax — Finance & Fintech HTML Template](https://preview.themeforest.net/item/plax-finance-fintech-startup-html-template/full_screen_preview/52942901)
- [Synox — Online Banking](https://html.xpressbuddy.com/synox/index_online_banking.html)
- [Awaiken — Fintech video landing](https://html.awaikenthemes.com/fintech/index-video.html)

Web research:

1. [WANDR Studio — Dark Mode Fintech Dashboard Design](https://www.wandr.studio/blog/dark-mode-fintech-dashboard-design)
2. [Foundey — Fintech Dashboard Design 2026](https://foundey.com/blog/fintech-dashboard-design-2026)
3. [Art of Styleframe — Modern Dashboard UI 2026](https://artofstyleframe.com/blog/dashboard-design-patterns-web-apps/)
4. [USA Tech Trend — Fintech Websites Dark Mode Examples 2026](https://usatechtrend.com/fintech-websites-dark-mode-examples-15-stunning-designs-to-inspire-you-in-2026/)
5. [Webstacks — Fintech Websites: Design Trends & Best Practices](https://www.webstacks.com/blog/fintech-websites)
6. [Toimi — Top 10 Best SaaS Website Designs 2026](https://toimi.pro/blog/best-saas-website-designs/)
7. [Grid Rebels — 20 Best SaaS Website Designs in 2026](https://gridrebels.studio/post/20-best-saas-website-designs-in-2026-examples-that-actually-convert)
8. [Qream — Best Fintech Company Websites in 2026](https://theqream.com/blog/best-fintech-websites-2026)
9. [Striped Horse — Best SaaS Website Designs in 2026](https://www.stripedhorse.com/blog/best-saas-website-designs)
10. [Framiq — What Makes a Great SaaS Landing Page in 2026](https://framiq.app/blog/best-saas-landing-pages-2026)
11. [WSA — Top 10 Fintech UX Design Best Practices for 2026](https://wsa.design/news/top-10-fintech-ux-design-best-practices-for-2026)
12. [SCT Info — UI/UX Design for FinTech](https://www.sctinfo.com/blog/fintech-app-design)
13. [Procreator — 10 Smart UX Strategies for Fintech Product Design](https://procreator.design/blog/best-fintech-product-design-tips-growth/)
14. [TestPapas — Fintech UX Design in 2026](https://testpapas.com/blog/fintech-ux-design)
15. [Design Bootcamp — AI-UX in Fintech](https://medium.com/design-bootcamp/ai-ux-in-fintech-a-comprehensive-guide-55f84114c0a0)
