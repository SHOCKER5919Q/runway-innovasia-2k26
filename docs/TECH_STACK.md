# Tech stack

Every entry answers one question: *why this, and what would have been wrong with the
obvious alternative?*

## Backend

| Choice | Why | Alternative rejected |
|---|---|---|
| **Python 3.11+** | The quantitative stack lives here. A forecasting engine in a language without NumPy would be an exercise in reimplementation. | Node for one language across the stack — but then the Monte Carlo is hand-written and slow. |
| **FastAPI** | Typed request/response models, dependency injection that makes tenant scoping a parameter rather than a convention, and OpenAPI generated from the code. | Flask: no typing, no generated schema. Django: ORM and admin not needed; too much ceremony. |
| **SQLAlchemy 2.0** | Typed `Mapped[...]` columns, and portability between SQLite and PostgreSQL from one model definition. | Raw SQL: no portability. Prisma/Drizzle: wrong language. |
| **SQLite (default)** | The project runs with one command and no infrastructure. Nothing about the ORM is SQLite-specific. | Postgres by default: correct for production, hostile for evaluation. |
| **Pydantic v2 + pydantic-settings** | Validation at the edge; configuration in one typed object. Nothing in the engine reads `os.environ`. | `dataclasses` + manual validation: more code, worse errors. |
| **NumPy** | The Monte Carlo engine. 4,000 paths × 14 weeks vectorised runs in ~50 ms. | Pure Python: ~100× slower, and the Scenario Lab stops feeling interactive. |
| **scikit-learn** | `GradientBoostingRegressor` with `quantile` and `absolute_error` losses. Small-data friendly, deterministic with a seed, and its per-feature behaviour can be probed by ablation. | PyTorch/LightGBM: more capable, but on a few hundred invoices the bottleneck is data, not model class — and an extra native dependency buys nothing. |
| **SciPy / pandas** | Distributions, significance tests, time-series grouping. | Hand-rolled statistics: more code, more bugs. |
| **PyJWT** | Stateless bearer tokens. | Server-side sessions: needs a shared store the architecture is otherwise free of. |
| **hashlib PBKDF2-HMAC-SHA256** | No native build dependency; 240,000 iterations; accepted under NIST SP 800-63B. | argon2id/bcrypt: stronger and the documented production target, but each adds a compiled wheel that can fail to install on a fresh machine — the exact failure that stops someone evaluating the project. |
| **pytest** | 191 tests, parametrised. | unittest: more boilerplate for the same coverage. |

### Libraries deliberately not used

| Library | Why not |
|---|---|
| **MAPIE** | Split conformal prediction for a single quantile model is ~15 lines. The library is built for a broader surface than is needed here, and `app/forecast/payment_delay.py` shows the arithmetic in place rather than hiding it behind an import. |
| **Riskfolio-Lib / PyPortfolioOpt** | Both optimise portfolio *weights* under asset-return covariance. RUNWAY has no weights to optimise — it has a cash path. The genuinely transferable ideas (VaR, CVaR, HHI, common random numbers) are each a handful of lines. Importing a portfolio optimiser to borrow a percentile would be cargo cult. |
| **ruptures** | Change-point detection. The spend-shift detector is a two-sample t-test on a 6-week window, which is interpretable in one sentence. `ruptures` is better for *finding unknown* change points in long series; this is a *known* window. |
| **River** | Online learning. The data arrives in batches (an import), not a stream. |
| **SHAP** | Per-feature contributions are computed by single-feature ablation against the training mean — model-agnostic, deterministic, and the same shape of answer. Exact SHAP on a 300-tree GBM is slower and adds a dependency for an explanation that is already explainable. |
| **Chronos-2 / foundation forecasters** | Evaluated and rejected for the *primary* path, on principle: the next 13 weeks of an MSME's cash are dominated by a few hundred invoices and obligations whose dates and amounts are already known. A sequence model trained on generic time series throws that information away. Statistical estimation is used where it belongs — the unknown residual, the sales not yet invoiced — where it is a robust de-seasonalised median with a damped trend. A foundation model is a reasonable upgrade *for that component* once there is more history. |

## Frontend

| Choice | Why | Alternative rejected |
|---|---|---|
| **Next.js 16, App Router** | File-based routing for 21 screens, static generation where possible, and a dev-time proxy that makes `/api/*` same-origin so CORS never interferes with a demo. | Vite SPA: would need its own router and a CORS story. |
| **React 19** | — | — |
| **TypeScript strict** | The production build type-checks and fails on error. `ignoreBuildErrors` is **off**, unlike the reference bundle it started from. | Loose TS: the errors still exist, you just meet them later. |
| **Tailwind CSS v4** | Design tokens as CSS custom properties in **OKLCH**. Light and dark are one token set redefined under a selector, not two stylesheets. OKLCH keeps perceived lightness stable across hues, so the chart palette does not have one series visually shouting. | CSS modules: no token system. v3: no native OKLCH or `@theme`. |
| **Motion (Framer Motion 12)** | Layout animations (`layoutId` for the sliding nav indicator), presence transitions for expanding evidence panels, and `useInView` reveals. | CSS-only: cannot do shared-element transitions. |
| **GSAP + ScrollTrigger** | Scroll-linked sequencing on the marketing surface, synchronised with Lenis via `ScrollTrigger.update` and `gsap.ticker.lagSmoothing(0)`. Loaded dynamically, so it is not in the app bundle. | Motion's `useScroll` alone: fine for parallax, weaker for timelines. |
| **Lenis** | Inertial smooth scrolling on the landing page. Keeps `position: sticky` and keyboard navigation working, which naive scroll-jacking breaks. **Not used anywhere inside the app** — hijacking scroll in a financial table is hostile. | A CSS `scroll-behavior`: no inertia, no GSAP integration. |
| **Recharts** | Composable enough to draw a P10–P90 band as a genuine area between two series rather than a shaded approximation, and to overlay actual/predicted/simulated with different stroke treatments on one axis. | Chart.js: imperative, harder to compose. D3 directly: more control than is needed, much more code. |
| **lucide-react** | Consistent 24px grid icons, tree-shaken. | Icon fonts: no tree shaking, worse accessibility. |
| **clsx + tailwind-merge** | Conditional classes without specificity fights. | Template strings: last-wins conflicts. |

### Not used

A **component kit** (shadcn/ui, MUI, Chakra). The reference bundle shipped ~60
shadcn components; 60 were unused after the screens were built on hand-written
primitives, so they were removed along with ~25 Radix dependencies. Accessibility
is handled directly — `focus-visible` rings on every interactive element, `aria-*`
on every disclosure, `aria-current` on navigation, `aria-pressed` on toggles,
`role="alert"` on errors, a skip link, keyboard handling on the command palette,
and colour never used as the only channel for meaning.

A **data-fetching cache** (TanStack Query, SWR). The dataset is small, the backend
already caches on a content fingerprint, and a stale financial figure is worse than
a second request. `lib/use-api.ts` is 50 lines.

**React Bits.** Evaluated as suggested. Its value is copy-paste motion components;
the three that fit — scroll reveal, text reveal, pointer spotlight — are implemented
directly in `components/runway/motion.tsx` in ~120 lines, with
`prefers-reduced-motion` honoured in JavaScript so it also disables Lenis and the
GSAP ticker rather than only the CSS.

## Fonts

| Font | Role | Why |
|---|---|---|
| **Sora** | Display — headings, figures | Geometric, slightly editorial. Gives numerals presence without the generic-SaaS feel of Inter-everywhere. |
| **Inter** | Body, UI | Unmatched legibility at 11–14px, which is most of this interface. |
| **JetBrains Mono** | References, fingerprints, code | Clear zero, unambiguous `1Il`. |

`font-variant-numeric: tabular-nums` is applied to every element that can display a
changing number. Without it, a refresh makes the layout twitch — which reads as
instability in a product whose entire job is to look trustworthy.
