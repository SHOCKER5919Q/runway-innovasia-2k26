# Roadmap

Ordered by what unblocks the most, not by what is most interesting.

---

## Done since the first release

| Item | Outcome |
|---|---|
| **Alembic migrations** | `env.py` reads the URL from the app's own settings; SQLite gets batch mode automatically so one revision runs on both backends. |
| **Verified PostgreSQL path** | Schema migrated, full workspace seeded, identical 210-test suite green. Found three `VARCHAR` overflows SQLite was hiding, and one SQLite-only function in a test. |
| **Schema audit** | `scripts/audit_schema.py` checks every column against both the stored data and the code's own vocabulary. Wired into the suite so the class of bug cannot return. |
| **PDF invoice import** | Text-layer extraction with per-field confidence; OCR for scans via tesseract when present. Refuses rather than guesses. |
| **26-week cross-check** | Run-rate-changing scenarios are re-run over two quarters instead of the bias merely being disclosed. |
| **Frontend test suite** | 75 tests across formatting, component accessibility, the API client and navigation. |

---

## Now — production readiness

Nothing below this line matters for a deployment that holds real data until these
are done.

| | Item | Why first |
|---|---|---|
| 1 | **Encryption at rest + secrets management** | `RUNWAY_SECRET_KEY` has a committed default. See `SECURITY.md`. |
| 2 | **MFA for owner accounts** | Financial data, single factor. |
| 3 | **DPDP erasure workflow** | A legal obligation with statutory retention carve-outs, not a delete button. |
| 4 | **Shared cache and rate limiter** | Both are in-process; a second instance breaks both. |
| 5 | **Backup and tested restore** | Untested backups are not backups. |

---

## Next — closing the gaps the product still admits

| Item | What it fixes |
|---|---|
| **Background worker** | So an import returns immediately rather than waiting ~5 s for a state rebuild. |
| **Browser tests** | Nothing currently drives a real browser through the signature demonstration. |
| **More backfilled forecast runs** | Long-horizon coverage is reported on two observations. More history makes it measurable rather than merely stated with its sample size. |
| **Revenue–delay correlation** | In a downturn both worsen together. Modelled independently today; the most defensible single modelling addition. |
| **Chart-layer tests** | Recharts needs layout, which jsdom does not provide. Needs a real browser runner. |

---

## Then — integrations, in order of leverage

| Integration | Blocker | Why this order |
|---|---|---|
| **Payment gateway webhooks** | Merchant account and a public endpoint | Lowest barrier, immediate value — settlements arrive continuously |
| **Tally live connector** | A local agent | Most MSMEs already run Tally; the XML path already works |
| **GST via a GSP** | A GSP contract | Removes manual register upload and makes the liability estimate verifiable |
| **WhatsApp briefing** | Business Cloud API and approved templates | The briefing already exists server-side. This is the delivery channel for the daily habit the product depends on |
| **Account Aggregator** | Regulated-entity eligibility or a TSP arrangement | Highest value, highest barrier. The adapter and data model are already built |
| **TReDS** | Platform agreement and buyer acceptance | The economics are already modelled; this turns a recommendation into an action |

---

## Later — capability

**Industry depth.** Four profiles exist. Manufacturing needs production cycles and
work-in-progress; retail needs daily collections and inventory turns; services need
project-based revenue recognition.

**Inventory-aware forecasting.** The single largest missing input. The twin lists it
as absent today. Connecting it turns the cash-conversion cycle from DSO − DPO into
a real measurement.

**Multi-branch consolidation.** Group-level cash with inter-branch transfers
eliminated.

**Benchmarking.** "Your DSO is 64 days; the median for wholesale distribution in
Telangana is 48." This is a **privacy design problem before it is an engineering
one** — it needs consented, k-anonymous or differentially private aggregation, never
a cross-tenant join. It is not built, and it will not be built the easy way.

**Richer payment-delay features.** GST filing behaviour of the buyer, dispute and
credit-note history, sector indices. This is what would most plausibly let the
learned model finally beat its baseline.

**t-copula for tail dependence.** More faithful for joint extremes than the Gaussian
copula in use. Needs more data to estimate the degrees of freedom than is currently
available.

---

## Distribution

**Accountants first.** A CA serving twenty MSMEs has the data, the trust and the
recurring "can I afford this?" conversation. The accountant workspace exists for
this reason. Needs: client onboarding, bulk import, white-label reporting.

**Then accounting software partnerships** — RUNWAY as an intelligence layer inside
Tally or Vyapar rather than beside it.

**Then lenders and NBFCs** — the Cash Health Passport as a richer, business-consented
alternative to a bank statement. Needs a standard format and lender-side validation.

**Then industry associations and MSME clusters** — where trust is collective and
one credible reference carries a hundred businesses.

---

## Explicitly not planned

| | Why |
|---|---|
| **Becoming an accounting system** | Tally is better at it, and asking an owner to migrate their books is asking them to take a risk for someone else's benefit. |
| **Lending directly** | A different business, a different licence, and a conflict of interest with advice. |
| **Selling data** | Stated in the product, in the shared report and in `SECURITY.md`. |
| **An autonomous agent that acts** | Approval is the product's central safety property. Removing it would remove the reason to trust anything else. |
| **A credit score** | The health indicator is deliberately *not* one, and calling it one would invite exactly the misreading the product exists to prevent. |
