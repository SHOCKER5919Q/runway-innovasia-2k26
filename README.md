<div align="center">

# RUNWAY

**The financial intelligence layer for Indian MSMEs.**

*See the business. Understand the future. Test the decision before you make it.*

INNOVASIA 2K26 · PS-04 · FinTech · Team SignalForge · Vasavi College of Engineering, Hyderabad

</div>

---

## What this is

Most financial software tells an MSME owner where their money **went**. RUNWAY is
built to tell them where their business is **going**, and to let them try a decision
out before it becomes real.

It does three things, and keeps them strictly apart:

| | | |
|---|---|---|
| **ACTUAL** | *What is happening?* | A reconciled ledger built from bank statements, invoices, GST registers and settlement files. Every figure traces back to a source row. |
| **PREDICTED** | *What is likely to happen?* | A 13-week cash projection assembled invoice-by-invoice and simulated thousands of times, with P10/P50/P90 bands whose accuracy is measured and published. |
| **SIMULATED** | *What could happen?* | Twelve decision scenarios branched off a fixed baseline, sharing its random draws so the difference you see is the decision rather than the noise. |

These are separated in the database, in the API and on screen. An estimate can never
be mistaken for a bank balance.

---

## Quick start

```bash
cd /home/shocker/INNOVASIA

./run.sh setup          # create the venv, install everything, seed the demo
./run.sh dev            # API on :8000, web app on :3000
```

Then open **http://localhost:3000** and sign in:

| Account | Password | What they see |
|---|---|---|
| `owner@runway.demo` | `demo1234` | Everything for Sri Lakshmi Industrial Supplies |
| `manager@runway.demo` | `demo1234` | Same business; cannot change policy |
| `ca@runway.demo` | `demo1234` | A two-client accountant portfolio |

<details>
<summary><b>All commands</b></summary>

```bash
./run.sh setup [A-E]    # install + seed a chosen demo scenario
./run.sh dev            # run API and web app together
./run.sh api            # API only          -> http://127.0.0.1:8000/docs
./run.sh web            # web app only      -> http://localhost:3000
./run.sh seed C         # regenerate the workspace under scenario C
./run.sh test           # 210 backend tests (SQLite)
./run.sh test-pg        # the identical suite against PostgreSQL
./run.sh test-web       # 75 frontend tests
./run.sh test-all       # both
./run.sh verify         # ~5,000 accounting-invariant checks
./run.sh audit-schema   # every VARCHAR checked against what the code can write
./run.sh evaluate       # regenerate every published accuracy figure
./run.sh migrate        # apply Alembic migrations
./run.sh build          # production build of the web app
```

`make setup`, `make dev`, `make test` … work identically.

Running the pieces by hand:

```bash
# API
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# web app
cd frontend && pnpm dev

# seed a specific scenario at a specific date
cd backend && .venv/bin/python -m app.seed.seed --scenario D --reset --date 2026-11-07
```

</details>

**Requirements:** Python 3.11+, Node 20+, and `pnpm` or `npm`. Nothing else — the
default database is SQLite, so there is no Postgres, Redis or Docker to stand up.

**PostgreSQL is supported and verified**, not merely claimed. The schema migrates,
the full workspace seeds, and the identical 210-test suite passes against it:

```bash
createdb runway
export RUNWAY_DATABASE_URL="postgresql+psycopg:///runway?host=/run/postgresql"
./run.sh migrate && ./run.sh seed B && ./run.sh test-pg
```

Optional: `tesseract-ocr` and `poppler-utils`, only if you need to read *scanned*
PDF invoices. Text-layer PDFs work with no extra setup.

---

## The signature demonstration

Sign in as the owner and follow this path. It takes about four minutes.

1. **Home.** The briefing opens with available cash — not the bank balance, but
   cash less lien-marked and already-committed money. Beneath it, the 13-week
   projection with its uncertainty band.
2. **Customers.** ABC Distributors is 29% of revenue and pays, on average, 22 days
   beyond terms. That figure comes from 200 settled invoices; open invoices are
   excluded because an unpaid invoice says nothing about how fast someone pays.
3. **Risk Centre.** The engine has already connected those two facts: a buyer
   concentration alert, a receivables-ageing alert, and a stress test showing the
   business does not survive a 30-day market-wide payment slowdown even after
   drawing its overdraft.
4. **Scenario Lab → "Accept a new order".** A ₹15 lakh order at 18% margin on
   60-day terms. RUNWAY does not answer with the profit. It answers with the
   **funding gap**: ₹12.3 lakh of materials payable on day 37, against a balance
   collected on day 88. Minimum cash falls from ₹11.07L to ₹1.79L and the chance of
   breaching the safety buffer rises from 17% to 55%.
5. **Change the advance to 30%** and re-run. Minimum cash recovers to ₹6.24L and the
   breach probability drops to 35%. Same order, same margin, different financing.
6. **Optimise.** Rank *accept as-is*, *accept with advance*, *discount receivables*
   and *take a loan* on one risk-adjusted objective. Two of them are marked
   infeasible with the policy they breach named.
7. **AI Copilot.** Ask *"Should I accept a ₹15 lakh order on 60-day terms?"* in plain
   English and get the same numbers, labelled **SIMULATED**, with the evidence.

Every number on that path is computed from the ledger at request time. None is
stored in the frontend, and none is specific to a scenario.

---

## What makes it different

**It separates reality from expectation.** Three states, three storage models, three
visual treatments. The forecast is never drawn with the same line as the bank balance.

**It is portable, and proves it.** The same 210 tests pass on SQLite and PostgreSQL.
Getting there found three `VARCHAR` overflows that SQLite silently tolerates and
Postgres rejects — two of which the demo data never exercised. `./run.sh audit-schema`
now makes that class of bug impossible to reintroduce.

**It refuses to invent accuracy.** `scripts/evaluate_models.py` regenerates every
accuracy figure the product shows. On the demo book the gradient-boosted
payment-delay model beats its per-customer-median baseline by 3.2% — which a paired
test says is indistinguishable from noise (t = +1.29), so **RUNWAY ships the simpler
estimator and says so on screen**. A product that only reports wins is not reporting.

**Its copilot cannot make a number up.** Questions route to deterministic tools by
pattern matching before any model is involved. The model receives the tools' JSON and
writes prose. Every rupee figure in a reply is checked against that JSON; one that
is not there causes the reply to be discarded.

**It never acts on your behalf.** No payment, no credit application, no contract
change. Borrowing is only ever presented with its cost placed beside the cost of the
shortfall it would cover, and only after the free options.

**It is honest about what it is not connected to.** No live Account Aggregator, GST
or TReDS connection is claimed. The Integrations screen states, per connector,
exactly what would be required — including that an FIU arrangement needs the operator
to be an RBI/SEBI/IRDAI/PFRDA-regulated entity.

---

## How it works

```
 bank CSV · Tally XML · GST register · gateway settlements · manual entry
                                  │
                        ┌─────────▼─────────┐
                        │  INGESTION        │  parse → fingerprint → dedupe
                        └─────────┬─────────┘
                        ┌─────────▼─────────┐
                        │  UNIFIED LEDGER   │  normalise → resolve counterparty
                        │                   │  → classify → match to invoices
                        └─────────┬─────────┘
          ┌───────────────────────┼───────────────────────┐
┌─────────▼────────┐   ┌──────────▼─────────┐   ┌─────────▼────────┐
│  ACTUAL STATE    │──▶│  PREDICTED STATE   │──▶│ SIMULATED STATE  │
│  versioned,      │   │  payment-delay     │   │  scenario engine │
│  fingerprinted   │   │  model + Monte     │   │  + counterfactual│
│                  │   │  Carlo, versioned  │   │  + optimiser     │
└─────────┬────────┘   └──────────┬─────────┘   └─────────┬────────┘
          └───────────────────────┼───────────────────────┘
                        ┌─────────▼─────────┐
                        │ RISK · HEALTH ·   │
                        │ RECOMMENDATIONS   │
                        └─────────┬─────────┘
               ┌──────────────────┴──────────────────┐
     ┌─────────▼────────┐                  ┌─────────▼────────┐
     │  REST API (62)   │                  │  AI COPILOT      │
     └─────────┬────────┘                  │  22 typed tools  │
               │                           └─────────┬────────┘
               └──────────────┬──────────────────────┘
                   ┌──────────▼──────────┐
                   │  Next.js web app    │  21 screens
                   └─────────────────────┘
```

`docs/ARCHITECTURE.md` has the full picture, including why there is no Redis, no
Celery and no graph database.

---

## The formulas that do the work

Every one of these is implemented, tested and used — not described and skipped.

### 1. Cash available, not cash held

```
available liquidity = cash − restricted − committed
```
`backend/app/analytics/cash.py`. A lien-marked fixed deposit cannot pay payroll, and
GST already reserved is not spendable. Overdraft headroom is reported *separately*
because it is credit, not cash. **An unpaid invoice never enters any of these.**

### 2. The 13-week projection

```
closing[w] = closing[w−1]
           + collections from open invoices predicted to land in week w
           + collections from sales not yet invoiced (run-rate × seasonality)
           − payments on open purchase invoices due in week w
           − purchases supporting the forecast sales (COGS, lead-shifted)
           − obligations due in week w (GST, payroll, rent, EMI)
           − recurring operating costs from the trailing ledger
```
`backend/app/forecast/cashflow.py`. Ledger-driven, not a curve fitted to past
balances: the next quarter is dominated by a few hundred invoices and obligations
whose dates are already known, and a statistical extrapolation throws that away.
Time-series estimation is used where it belongs — on the *unknown* residual, the
sales not yet invoiced.

### 3. Correlated payment delays — a single-factor copula

```
delay_i = μ_i + σ_i · (√ρ · Z + √(1−ρ) · ε_i)
```
`backend/app/forecast/monte_carlo.py`. `Z` is one market-wide factor shared by every
customer on a given path. Treating delays as independent is the classic
understatement of liquidity risk: when the market is tight, everybody pays late at
once. `ρ` is estimated from the business's own monthly delay series and falls back to
0.25 with the reason stated in the output.

### 4. Common random numbers

Baseline and scenario are simulated with the **same seed and therefore the same
draws**, so the difference between them is attributable to the decision. Without
this, a 0.3-week runway difference is indistinguishable from sampling noise. It is
standard variance reduction, and it is what makes the Scenario Lab trustworthy.

### 5. Liquidity VaR and CVaR — borrowed from market risk

```
loss      = max(0, safety_buffer − min_weekly_cash)
VaR(95%)  = 95th percentile of loss
CVaR(95%) = mean of loss in the tail beyond VaR
```
VaR says *how bad a bad quarter looks*; CVaR says *how bad it gets when it goes bad*.
Explicitly labelled an operational liquidity measure adapted from market-risk VaR —
it is **not** a regulated investment VaR and carries no regulatory meaning.

### 6. Conformal calibration of prediction intervals

Quantile regression is not calibrated out of the box. A split-conformal step rescales
the band on a held-out slice:

```
nonconformity_i = max( (q50−y_i)/(q50−q10), (y_i−q50)/(q90−q50) )
scale           = ⌈(n+1)·0.80⌉-th smallest nonconformity
```
`backend/app/forecast/payment_delay.py`. On the demo book this lifts P10–P90 coverage
from **61% to 84%** against an 80% target. Without it, "P10–P90" is decoration.

### 7. Model selection by paired significance test

```
diff_i = |baseline_error_i| − |stacked_error_i|
ship    iff  t = mean(diff)/SE(diff) ≥ 1.96  AND  relative gain ≥ 2%
```
The two predictors score the *same* invoices, so the test is on the per-invoice
difference, not on two error distributions. This is the mechanism that stops a
fashionable model shipping when a median would do.

### 8. Herfindahl-Hirschman concentration

```
HHI = Σ (share_i)²          effective counterparties = 1 / HHI
```
From portfolio single-name risk. "The equivalent of 4.9 equally-sized customers carry
this book" is a sentence an owner can act on; "HHI 0.205" is not. Both are shown.

### 9. Robust outlier detection

```
robust z = (x − median) / (1.4826 · MAD)
```
Median/MAD rather than mean/sd, because the mean and standard deviation are dragged
by the very outliers being looked for. The 1.4826 makes MAD a consistent estimator of
σ for normal data. Isolation Forest is available as a cross-check but is reported as
*information only* — an unexplainable alert about someone's money destroys trust.

### 10. Early-payment discount, annualised

```
effective annual cost of forgoing = (d / (1 − d)) × (365 / days_saved)
```
A 2% discount for paying 20 days early is a **44.6% annualised** return on that cash.
RUNWAY compares it against the business's own borrowing-cost ceiling before
recommending it — and only if the forecast says the cash is genuinely spare that week.

### 11. MSMED §15 and Income-tax §43B(h)

```
statutory deadline = issue_date + min(agreed_credit_days, 45 if written agreement else 15)
effective due      = min(contractual_due_date, statutory_deadline)
```
Applies only to **micro and small** suppliers; medium enterprises are outside the
rule. The forecast schedules payables at the *effective* due date, and the scenario
engine refuses to defer protected invoices unless the owner explicitly overrides it.

### 12. Committed purchasing under a demand shock

A revenue drop cuts collections long before it cuts cash out: materials for the next
few weeks are already ordered. RUNWAY holds purchasing at the pre-shock level through
the lead-plus-terms window, then tapers. **Without this, "revenue falls 20%" comes out
as a cash improvement** — which is both wrong and dangerous to show an owner.

### 12b. The 26-week cross-check

Even with committed purchasing, a 13-week window is biased for any scenario that
changes the sales run-rate: purchases are paid in ~42 days while the collections
they fund arrive at ~53. So those scenarios are **re-run over 26 weeks** and both
figures are shown. On the demo book a 20% revenue drop costs ₹3.5 lakh over one
quarter and **₹7.5 lakh over two** — the panel says which quarter the damage lands
in. 13 weeks stays the primary horizon because it is the one an owner can act
within.

### 13. Risk-adjusted decision utility

```
utility = w_liq·Δliquidity + w_profit·profit − w_risk·Δdownside − w_cost·financing_cost
```
Weights come from the business's declared risk appetite and are returned with the
result, along with every term. The engine ranks; it explicitly does not decide.

### 14. Exact money

Every amount is an **integer number of paise**. Floats appear only inside statistical
models, and anything crossing back into the ledger is rounded once. Proportional
splits use the largest-remainder method so no paise is ever lost. This is why
`opening + credits − debits = closing` holds exactly across ~5,000 checks.

---

## Libraries, and what each is actually for

### Backend

| Library | Used for |
|---|---|
| **FastAPI** | The 62-endpoint REST API. Chosen for typed request/response models and OpenAPI generated from the code rather than maintained beside it. |
| **Uvicorn** | ASGI server. |
| **SQLAlchemy 2.0** | ORM with typed `Mapped[...]` columns. Models are written portably so the same code runs on SQLite (default, zero-setup) and PostgreSQL. |
| **Pydantic v2 / pydantic-settings** | Request validation and environment configuration. Nothing in the engine reads `os.environ` directly. |
| **NumPy** | The Monte Carlo engine. All 4,000 paths × 14 weeks are vectorised — a full simulation runs in ~50 ms, which is what makes the Scenario Lab feel immediate. |
| **pandas** | Time-series grouping during data preparation. |
| **SciPy** | Statistical distributions and the significance tests behind model selection. |
| **scikit-learn** | `GradientBoostingRegressor` with quantile and absolute-error losses for payment-delay prediction; `IsolationForest` as a secondary anomaly cross-check. Chosen over a neural model because the dataset is hundreds to a few thousand invoices and the relationships are near-monotone. |
| **PyJWT** | Stateless bearer tokens. |
| **hashlib (stdlib)** | PBKDF2-HMAC-SHA256 password hashing at 240,000 iterations — no native build dependency, and an accepted choice under NIST SP 800-63B. argon2id is the documented production target. |
| **httpx** | Optional calls to the Anthropic API from the copilot's explanation layer. |
| **Alembic** | Schema migrations. `env.py` reads the URL from the application's own settings, so a migration can never target a different database than the app. SQLite gets batch mode automatically, which is what lets one revision script run on both backends. |
| **pypdf** | Text-layer PDF invoice extraction — GST e-invoices, Tally, Zoho, Busy. |
| **tesseract / poppler** (system, optional) | OCR for *scanned* PDFs. Shelled out to rather than imported, because the binary has to be installed either way and this keeps the Python dependency list clean. |
| **psycopg 3** | PostgreSQL driver. Optional; the default is SQLite. |
| **pytest** | 210 tests, green on both SQLite and PostgreSQL. |

Conformal prediction, Monte Carlo, VaR/CVaR, HHI and the stress-test harness are
**implemented directly** rather than pulled from MAPIE, Riskfolio-Lib or
PyPortfolioOpt. Those libraries are built around asset returns and portfolio weights;
the adaptation surface to MSME liquidity is small enough that a direct implementation
is shorter, auditable and dependency-free. `docs/QUANT_METHODS.md` records that
decision per technique.

### Frontend

| Library | Used for |
|---|---|
| **Next.js 16** (App Router, Turbopack) | 21 screens, static where possible. It also proxies `/api/*` to the backend, so the browser makes same-origin requests and CORS never interferes with a demo. |
| **React 19** | UI. |
| **TypeScript 5.7** | Strict. The production build type-checks and fails on an error — `ignoreBuildErrors` is **off**. |
| **Tailwind CSS v4** | Design tokens as CSS custom properties, so light and dark are one token set rather than two stylesheets. The values are the literal hex from `DESIGN.md` (see *Design system* below) rather than computed OKLCH, because a design system a human maintains should be greppable against the document it came from. |
| **Motion** (Framer Motion 12) | Component-level transitions: page changes, the sliding nav indicator, expanding evidence panels, staggered reveals. One animation runtime inside the app bundle. |
| **GSAP + ScrollTrigger** | Scroll-linked work on the marketing surface: the pinned three-state card cycle and the pinned decision scrollytelling. Lenis is driven *from* `gsap.ticker` rather than its own `requestAnimationFrame` loop — two clocks let Lenis move the scroll position in a frame ScrollTrigger has already measured, which makes a pinned section shiver. Pins are also re-measured on `document.fonts` `loadingdone`, since a late web font changes the laid-out height the pin's end was computed from. |
| **Lenis** | Inertial smooth scrolling — **on the landing page only**. Hijacking scroll inside a financial table is hostile; people scan tables, they do not glide through them. |
| **three.js + @react-three/fiber + drei** | The landing hero: three refracting glass panels over two layers of lit bars, `MeshTransmissionMaterial` for real transmission and chromatic aberration. Loaded `ssr: false` behind a static CSS fallback, paused via IntersectionObserver when off-screen, and skipped entirely on a coarse pointer, ≤4 cores, <820px or `saveData`. Chosen over a generated GLB (Meshy and similar): ~8KB of code against a multi-MB static mesh, and it responds to scroll and pointer, which a baked mesh cannot. |
| **Recharts** | The uncertainty-band chart, flow bars, ageing, concentration, the health gauge, sparklines and the customer risk scatter. Composable enough to draw a P10–P90 band as a real area between two series. |
| **lucide-react** | Icons. |
| **clsx + tailwind-merge** | Conditional classes without specificity fights. |

| **Vitest + Testing Library** | 92 frontend tests: Indian number formatting, component accessibility, the API client's tenant and as-of handling, navigation integrity, and the shared-passport value renderer (a fraction must never print as a count, money must never lose its denomination). jsdom environment. |

Deliberately **not** used: a component kit (the screens are built on hand-written
accessible primitives, so the bundle carries nothing unused), a data-fetching cache
library (the dataset is small and a stale financial figure is worse than a second
request), and any animation on a live financial figure (an animating balance is
unreadable at exactly the moment it matters).

**React Bits** was evaluated as the user suggested. Its value is copy-paste motion
components, and the three that fit here — a scroll reveal, a text reveal and a
pointer spotlight — are implemented directly in `components/runway/motion.tsx` in
about 120 lines, with `prefers-reduced-motion` honoured in JavaScript (which also
disables Lenis and the GSAP ticker, not just the CSS). Taking the dependency would
have added weight without adding behaviour.

---

## Design system

`DESIGN.md` at the repository root is the single source for colour, type and
spacing. It is Linear's structure with the accent replaced by lime `#C6F54A`,
and it records its two deliberate departures from that structure rather than
leaving them to be rediscovered:

1. **Lime, not lavender.** The reference boards this was designed against are
   green, and violet reads as a default.
2. **A semantic set exists at all.** Linear has no "good" and "bad" colour. A
   financial product must distinguish a gain from a loss, so `semantic-gain`,
   `semantic-loss` and `semantic-warn` are defined — each one always paired
   with a glyph, never carried by colour alone.

The accent is reserved for brand, CTA and focus. It never means "good". The
three states have their own fixed channel — ACTUAL cyan and solid, PREDICTED
lime as a band, SIMULATED amber and dashed — which is why the accent cannot
also be a verdict.

The system's central rule is that **real product UI is the protagonist**. The
landing page's `#product` section is not a screenshot: it mounts the same
`Stat`, `Panel`, `StateBadge`, `CashBandChart`, `BreachBars` and `HealthGauge`
the application mounts, against the demo tenant's figures, with three working
levers that redraw all three states in one frame. If a chart regresses in the
app it regresses on the landing page too.

Attribution: the analysis `DESIGN.md` was derived from is
[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (MIT).

## The premium layer

Scroll and motion work, and what each piece is for. Everything here collapses
to nothing under `prefers-reduced-motion`, and none of it is load-bearing —
delete the block from `globals.css` and every screen still reads correctly.

| Piece | Where | What it does |
|---|---|---|
| `rw-stage` cascade | all 21 app screens + the shared report | A CSS `nth-child` cascade on the route wrapper's grandchildren, so a screen *assembles* instead of appearing. Keyed in CSS rather than per-page code, which is why 20 screens inherited it without a line of edits. Delays flatten after the eighth child — nobody should wait on decoration. |
| `rw-route-bar` | app shell | A one-sweep progress bar, remounted on each navigation so it cannot get stuck. A navigation that recomputes a forecast is not instant; saying so beats a frozen screen. |
| `IntroCurtain` | landing | One brand beat on first arrival, gated on `sessionStorage` so returning from `/login` does not replay it. Painted *over* an already-rendered page and removed by a timer that cannot fail to a blank screen. |
| `ChapterRail` | landing | A fixed section index that tracks the scroll. It picks the section with the largest visible share rather than firing on the last boundary crossed — the naive version flickers between two short adjacent sections. Every dot is a real anchor. |
| `hero3d` | landing, login | Refracting glass panels over lit bars. Capability-gated and paused off-screen. |
| GSAP pins | landing | The three-state card cycle and the decision scrollytelling, both driven from the unified Lenis/GSAP ticker. |
| Print stylesheet | shared report | A passport gets printed and filed by a lender, so print forces the light ladder, drops the chrome and keeps panels off page breaks. |

The marketing motion components in `components/runway/bits.tsx` — magnetic
buttons, scrambling counters, tilt cards — are **not used anywhere inside the
application**, by rule. A scrambling number is delightful on a landing page and
hostile next to someone's bank balance.

---

## Repository layout

```
INNOVASIA/
├── run.sh  Makefile              one-command setup, run, test, verify
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── core/                 config, db, money (integer paise), security, enums
│       ├── models/               28 SQLAlchemy tables
│       ├── ledger/               normalise, classify, resolve, reconcile, as-of
│       ├── analytics/            cash, receivables, payables, health, obligations,
│       │                         concentration, anomaly
│       ├── forecast/             features, payment_delay, cashflow, monte_carlo
│       ├── risk/                 stress tests, early-warning engine
│       ├── digital_twin/         state builder, graph, timeline, scenario engine,
│       │                         decision optimiser, twin service
│       ├── financial_states/     the three-state manager, versioning, reconciliation
│       ├── recommend/            deterministic recommendation engine
│       ├── copilot/              tools, router, LLM layer, service
│       ├── integrations/         adapter framework + 6 importers
│       ├── api/                  8 route modules, 62 endpoints
├── frontend/
│   ├── app/                      21 routes
│   ├── components/runway/        shell, primitives, charts, motion
│   ├── lib/                      api client, formatting, hooks
│   └── tests/                    75 frontend tests
│       ├── migrations/           Alembic revisions
│       └── seed/                 synthetic MSME generator, 5 scenarios
├── tests/                        210 backend tests across 9 files
├── scripts/                      evaluate_models.py, verify_ledger.py, audit_schema.py
├── docs/                         32 documents
└── Reference/                    the supplied design board (unmodified)
```

---

## Documentation

| | |
|---|---|
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | What is built, what is not, and every known limitation |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and the decisions behind it |
| [`docs/THREE_STATE_ARCHITECTURE.md`](docs/THREE_STATE_ARCHITECTURE.md) | The core invariant, and how it is enforced |
| [`docs/DIGITAL_TWIN_ARCHITECTURE.md`](docs/DIGITAL_TWIN_ARCHITECTURE.md) | The twin's structure and lifecycle |
| [`docs/DIGITAL_TWIN_MATHEMATICS.md`](docs/DIGITAL_TWIN_MATHEMATICS.md) | Every formula, with worked examples |
| [`docs/ML_METHODOLOGY.md`](docs/ML_METHODOLOGY.md) | Features, leakage control, calibration, model selection |
| [`docs/EVALUATION_RESULTS.md`](docs/EVALUATION_RESULTS.md) | Measured accuracy — regenerated by script |
| [`docs/QUANT_METHODS.md`](docs/QUANT_METHODS.md) | Each market technique borrowed, adapted and justified |
| [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) | All 62 endpoints |
| [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) | All 28 tables |
| [`docs/SECURITY.md`](docs/SECURITY.md) | What is implemented and what production still needs |
| [`docs/COMPLIANCE_NOTES.md`](docs/COMPLIANCE_NOTES.md) | AA, GST, MSMED, 43B(h), DPDP — with sources |
| [`docs/INTEGRATION_STATUS.md`](docs/INTEGRATION_STATUS.md) | Per connector: what works, what it would need |
| [`docs/COMPETITOR_ANALYSIS.md`](docs/COMPETITOR_ANALYSIS.md) | Where RUNWAY sits beside Tally, Vyapar, Zoho and the rest |
| [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md) | The scripted walkthrough and all five scenarios |
| [`docs/TESTING.md`](docs/TESTING.md) | What is tested and why those things |
| [`docs/REFERENCE_ANALYSIS.md`](docs/REFERENCE_ANALYSIS.md) | How the supplied design board became the design system |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | What comes next |

---

## Honest limitations

Read [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for the full list. The ones that matter
most:

- **No live financial connections.** Account Aggregator, GST GSP, TReDS and payment
  webhooks are built as adapters and exercised against sample payloads. None is
  connected, and nothing in the product says otherwise.
- **The learned payment-delay model does not currently beat its baseline.** On the
  demo book the per-customer median is statistically indistinguishable from the GBM,
  so RUNWAY ships the median. The selection machinery, not the model, is the result.
- **Long-horizon forecast coverage is weak and thinly measured.** Beyond six weeks
  the P10–P90 band contains the outcome less often than 80%, over very few
  observations. The number is shown with its `n` rather than hidden.
- **No inventory or order-book data.** The twin states this explicitly rather than
  inventing stock figures, and the cash-conversion metric says so on screen.
- **Single-process, in-memory cache and rate limiter.** Correct for one instance,
  not for a horizontally-scaled deployment. `docs/SECURITY.md` says what changes.
- **No browser tests.** 75 frontend unit and component tests, plus a backend e2e
  suite over the API the UI consumes — but nothing drives a real browser.
- **Scanned-PDF OCR needs system packages.** Text-layer PDFs need nothing extra.
- **Demo data is synthetic** and labelled as such on every screen, in the API and in
  the shared report.

---

<div align="center">
<sub>RUNWAY turns transactions into understanding, understanding into foresight,<br/>
and foresight into better decisions — without ever pretending to know more than it does.</sub>
</div>
