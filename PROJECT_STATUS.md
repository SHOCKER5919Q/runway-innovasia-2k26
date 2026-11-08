# PROJECT_STATUS

**Last updated:** 7 November 2026
**Phase:** 7 of 7 — testing and finalisation, complete
**Build state:** backend **210/210** tests passing on **both SQLite and PostgreSQL** ·
frontend **75/75** tests passing · production build clean with TypeScript checking on ·
~5,000 accounting-invariant checks passing · every VARCHAR column audited

This file records what exists, what does not, and every limitation worth knowing.
Nothing planned is described here as done.

---

## 1. Running services

| Service | Command | Address | State |
|---|---|---|---|
| API | `./run.sh api` | `http://127.0.0.1:8000` (`/docs`) | Working |
| Web app | `./run.sh web` | `http://localhost:3000` | Working |
| Both | `./run.sh dev` | as above | Working |
| Database | — | `data/runway.db` (SQLite) | Working. **PostgreSQL verified**: schema migrated, full workspace seeded, entire test suite green |
| Migrations | `./run.sh migrate` | Alembic | Working on both backends |

No external service is required for the default setup. There is no Redis, no Celery
broker, no Docker daemon and no object store in the current build.

PostgreSQL is **supported and verified**, not merely claimed:

```bash
createdb runway
RUNWAY_DATABASE_URL="postgresql+psycopg:///runway?host=/run/postgresql" ./run.sh migrate
RUNWAY_DATABASE_URL="postgresql+psycopg:///runway?host=/run/postgresql" ./run.sh seed B
./run.sh test-pg        # the identical 210-test suite, against Postgres
```

---

## 2. Completed work

### Phase 0 — discovery and architecture ✅
- Inspected `Reference/` in full: the UI board PNG and the shadcn/Next reference
  bundle. Both preserved unmodified. Analysis in `docs/REFERENCE_ANALYSIS.md`.
- Researched the AA/ReBIT framework, s.43B(h), MSMED s.15 and the competitor
  landscape. Sources recorded in `docs/COMPLIANCE_NOTES.md` and
  `docs/COMPETITOR_ANALYSIS.md`.
- Architecture settled and documented before any product code was written.

### Phase 1 — product foundation ✅
- Design system derived from the reference board (`frontend/app/globals.css`):
  OKLCH tokens, light and dark from one set, financial semantics separated from
  brand colour.
- Authentication: PBKDF2-HMAC-SHA256, JWT bearer tokens, four roles, per-business
  membership, purpose-scoped consent records.
- 28 ORM tables with tenant scoping, versioning and provenance columns.
- 21 frontend routes behind a shared shell with a command palette, business
  switcher, theme toggle and as-of date control.

### Phase 2 — unified financial intelligence ✅
- Importers: bank CSV (auto-detects Indian statement layouts), gateway settlement
  CSV (gross/fee/net), Tally voucher XML, GST register JSON/CSV, **PDF invoices
  (text layer, with OCR for scans when tesseract is present)**, manual entry, and
  a ReBIT-shaped AA sample parser.
- Narration normalisation, counterparty resolution with an explicit ambiguity
  threshold, 20-rule transparent classifier with per-row confidence.
- Reconciliation supporting partial payments, split settlements, gateway fees,
  refunds and reversals. Duplicate detection distinguishes a *hard* duplicate
  (shared bank reference) from a *suspected* one — the latter is flagged, never
  dropped. In-file duplicates are caught too.
- Point-in-time reconstruction (`app/ledger/asof.py`) so any date can be evaluated
  as it actually looked.

### Phase 3 — forecasting and risk ✅
- Leakage-safe feature pipeline, asserted by `tests/test_no_leakage.py`.
- Payment-delay model: quantile and L1 gradient boosting, stacked against a
  per-customer median, selected by a paired significance test, intervals calibrated
  by split conformal prediction.
- 13-week ledger-driven cash model with a vectorised Monte Carlo engine
  (~50 ms for 4,000 paths), single-factor correlated delays, committed-purchase
  modelling, and a **26-week secondary horizon** that re-runs run-rate-changing
  scenarios over two quarters instead of merely disclosing the truncation bias.
- Eight-dimension financial health score, fully configurable and fully explained.
- Liquidity VaR/CVaR, eight stress tests, sensitivity analysis, HHI concentration,
  correlation estimation, robust anomaly detection.

### Phase 4 — decision intelligence ✅
- Twelve scenario types, each a pure mutation of the forecast inputs.
- Counterfactual comparison under common random numbers.
- Risk-adjusted decision optimiser with published weights and policy constraints.
- Deterministic recommendation engine with an explainable five-term ranking.
- Obligation calendar with GST estimation and MSMED/43B(h) exposure.
- Cash Health Passport with per-section verification classes and revocable sharing.

### Phase 5 — AI experience ✅
- 22 typed copilot tools, each declaring the state it reads from.
- Deterministic intent routing before any model call.
- Optional LLM explanation layer with fencing of untrusted text and numeric
  verification of every reply.
- Daily financial briefing assembled from the same bundle as the dashboard.
- Five-language scaffolding and browser-native voice input.

### Phase 6 — advanced capabilities ✅
- Digital twin: state reconstruction, relationship graph, temporal timeline,
  activity log, validation and data-quality scoring.
- Three-state architecture with immutable versioning and forecast reconciliation.
- Four industry profiles driving both the generator and the forecaster's priors.
- Accountant multi-business workspace.

### Phase 7 — testing and finalisation ✅
- **210 backend tests** across money, ledger invariants, reconciliation, leakage,
  forecasting, three-state behaviour, PDF extraction, schema portability,
  API/security and the end-to-end workflow — green on SQLite *and* PostgreSQL.
- **75 frontend tests** across formatting, UI primitives, the API client and
  navigation.
- `scripts/verify_ledger.py` audits the books outside pytest.
- `scripts/evaluate_models.py` regenerates every published accuracy figure.
- `scripts/audit_schema.py` checks every VARCHAR against both the stored data and
  the code's own vocabulary — this found three real overflows SQLite was hiding.
- 32 documents.

---

## 3. Test results

```
$ ./run.sh test            # SQLite
210 passed in 75s

$ ./run.sh test-pg         # the identical suite, against PostgreSQL
210 passed in 83s

$ ./run.sh test-web        # frontend
75 passed in 1.2s
```

| File | Tests | Covers |
|---|---:|---|
| `test_money.py` | 20 | Integer-paise exactness, Indian grouping, lossless splits |
| `test_ledger_invariants.py` | 9 | Balance identity, no over-allocation, no money created |
| `test_reconciliation.py` | 24 | Duplicates, classification, entity resolution, partial payments, idempotence |
| `test_no_leakage.py` | 5 | Features recomputed with the future hidden are byte-identical |
| `test_forecast.py` | 17 | Quantile ordering, calibration, reproducibility, monotonicity |
| `test_three_state.py` | 10 | Versioning, scenario isolation, baseline pinning, MSMED protection |
| `test_api_and_security.py` | 61 | Every endpoint, tenant isolation, roles, consent revocation |
| `test_workflow_e2e.py` | 15 | The full story from import to recorded decision |
| `test_pdf_and_portability.py` | 19 | PDF field extraction, VARCHAR portability, the 26-week cross-check |

**Frontend** (`frontend/tests/`, `./run.sh test-web`)

| File | Tests | Covers |
|---|---:|---|
| `format.test.ts` | 27 | Indian digit grouping, compact lakh/crore, dates, deltas, state metadata |
| `primitives.test.tsx` | 28 | Accessibility, semantics, and the "colour is never the only channel" rule |
| `api.test.ts` | 13 | Tenant headers, as-of propagation, 401 handling, error shapes |
| `nav.test.ts` | 7 | No duplicate or dead routes, every item grouped and described |

```
$ ./run.sh verify
4,996 invariant checks run. All accounting invariants hold.

$ ./run.sh audit-schema
185 VARCHAR columns checked against stored data and the code's vocabulary.
Every VARCHAR column has room for what the code can write.
```

---

## 4. Measured accuracy

Regenerate with `./run.sh evaluate`. Full tables in `docs/EVALUATION_RESULTS.md`.

**Sri Lakshmi Industrial Supplies** (demo scenario B, as of 2026-11-07)

| Measure | Result |
|---|---|
| Payment-delay MAE, held-out chronological tail | **10.06 days** |
| Per-customer-median baseline | 10.06 days |
| Shipped predictor | the baseline — the GBM's 3.2% calibration gain failed the paired test (t = +1.29, needs ≥ 1.96) |
| Payment-date P10–P90 coverage, raw → conformal | 61% → **84%** (target 80%) |
| Realised payment predictions | 285 resolved, MAE **10.04 days**, coverage **88%** |
| Cash-forecast coverage, ≤ 4-week horizon | **100%** over 15 observations |
| Cash-forecast coverage, > 6-week horizon | ~50% over 4 observations — too few to conclude from, and shown with its `n` |
| Late-payment alert (> 15 days) | precision 0.68, recall 0.64 |

**That the learned model lost is the headline result**, not a footnote. The selection
machinery refused to ship it, the UI says so on the Cash Runway screen, and this
document says so here.

---

## 5. Known issues and limitations

### Modelling
1. **The payment-delay GBM does not beat its baseline** on either demo book. The
   per-customer median is near-Bayes-optimal when delays are close to i.i.d. per
   customer. On a real book with drift, size effects and seasonality, the stack
   would likely ship — the mechanism is in place and tested either way.
2. **Long-horizon interval coverage is below target.** Beyond six weeks, measured on
   2–4 observations. More backfilled runs would make it meaningful; the number is
   reported with its sample size rather than suppressed.
3. **Horizon truncation is now corrected, not merely disclosed.** A 13-week window
   sees the cash cost of a revenue change (purchases paid in ~42 days) before its
   collection effect (~53 days). Run-rate-changing scenarios are therefore re-run
   over **26 weeks** and both figures are shown. On the demo book a 20% revenue
   drop costs ₹3.5 lakh over one quarter and ₹7.5 lakh over two. The 13-week view
   remains the primary one because it is the horizon an owner can act within.
4. **Breach probability can fall under a revenue drop** because forecast volatility
   scales with sales volume. Directionally correct in isolation, potentially
   confusing in presentation. Closing cash, which falls monotonically, is the
   metric to read for that scenario.
5. **No inventory, order book or production data.** The twin lists these as missing
   rather than inventing them. Cash-conversion is therefore DSO − DPO with inventory
   days absent, and says so.
6. **GST liability is estimated** from output tax on recorded sales less input credit
   on recorded purchases. Labelled an estimate everywhere. QRMP filers, reverse
   charge, ineligible ITC and amendments are not modelled.

### Engineering
7. **Single-process cache and rate limiter.** Both are in-memory. Correct for one
   instance; a second instance needs a shared store.
8. **No background worker.** State rebuilds run inline, taking ~0.8 s warm and ~5 s
   cold. Acceptable at this scale; a queue is needed before it is not.
9. **No end-to-end browser tests.** There are 75 frontend unit and component tests,
   and the backend e2e suite covers the API contract the UI consumes, but nothing
   drives a real browser through the signature demonstration.
10. **Scanned-PDF OCR depends on system packages.** Text-layer PDFs work with no
    extra setup. Scans need `tesseract-ocr` and `poppler-utils`; when they are
    absent the importer says so instead of failing obscurely.
11. **PDF direction is inferred from the filename.** A single invoice PDF rarely
    states whether it is a sale or a purchase from the holder's point of view, so
    the adapter guesses from the filename, defaults to *purchase* (the safer
    error, since a wrong sales invoice would inflate receivables), and says so in
    the preview.

### Product
13. **No live integrations.** Listed per connector in `docs/INTEGRATION_STATUS.md`
    with exactly what each would require.
14. **WhatsApp briefing is not built.** The briefing is generated server-side and is
    renderable as text, which is the prerequisite — the delivery channel is not.
15. **Multi-language is scaffolding.** The copilot accepts a language and instructs
    the model accordingly; the interface itself is English only.
16. **Benchmarking against peer businesses is not built.** It would need a consented
    cross-tenant aggregation layer, which is a privacy design problem before it is an
    engineering one.

---

## 6. Integration status, in one line each

| Connector | Status | What it needs |
|---|---|---|
| Bank statement CSV | **Working** | A file you already have |
| PDF invoice (text layer) | **Working** | A file you already have |
| PDF invoice (scanned) | **Working** | `tesseract-ocr` and `poppler-utils` |
| Gateway settlement CSV | **Working** | A file you already have |
| Tally voucher XML | **Working** | Day Book → Export → XML |
| GST register JSON/CSV | **Working** | An export of the register |
| Manual entry | **Working** | — |
| AA sample payload | Parses samples | An FIU arrangement for live data |
| Account Aggregator (live) | Not connected | Operator must be an RBI/SEBI/IRDAI/PFRDA-regulated entity or work through one; NBFC-AA agreement; ReBIT client-standards adoption |
| GST via GSP | Not connected | GSP contract and per-GSTIN credentials |
| Payment gateway webhooks | Not connected | Merchant account, webhook secret, public HTTPS endpoint |
| Tally live connector | Not connected | Local agent on the Tally network |
| TReDS | Not connected | Seller onboarding, buyer acceptance, platform agreement |
| WhatsApp briefing | Not built | WhatsApp Business Cloud API and approved templates |

---

## 7. Next implementation task

In priority order:

1. **Background worker** for state rebuilds, so an import returns immediately
   rather than waiting ~5 s.
2. **Browser tests** driving the signature demonstration end to end.
3. **More backfilled forecast runs** so long-horizon accuracy becomes measurable
   rather than merely reported with its sample size.
4. **Encryption at rest and secrets management** — see `docs/SECURITY.md`.
5. **Revenue–delay correlation**: in a downturn both worsen together, and they are
   currently modelled independently.

---

## 8. Data provenance

Every figure in the running demo is computed at request time from a synthetic ledger
generated by `backend/app/seed/generator.py` under a fixed seed. The business is
marked `is_demo=True`, a ribbon says so on every screen, the API says so in
`/api/business`, and the Cash Health Passport declares it. **No real business's data
appears anywhere in this project.**
