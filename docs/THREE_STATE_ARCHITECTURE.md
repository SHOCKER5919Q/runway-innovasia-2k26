# The three-state architecture

> This is the core invariant of RUNWAY. Everything else is built on top of it.

## The problem it solves

An MSME owner opens a financial dashboard and sees ₹18 lakh. Three questions follow
immediately, and most tools answer none of them:

- Is that in the bank, or does it include invoices someone still owes me?
- Is it today's figure, or a projection?
- Does it assume the order I am thinking about accepting?

When reality, expectation and possibility share a screen without being distinguished,
the owner either learns to distrust every number or — worse — acts on one of them as
if it were the other.

RUNWAY therefore separates three states, **in the database, in the API and on
screen**:

| State | Question | What it is | Visual treatment |
|---|---|---|---|
| **ACTUAL** | What is happening? | Reconstructed from the reconciled ledger | Solid line, teal |
| **PREDICTED** | What is likely to happen? | Model output with an uncertainty band | Line + band, violet |
| **SIMULATED** | What could happen? | A scenario branched off a baseline | Dashed line, amber |

Each state has its own hue *and* its own line treatment, so colour is never the only
channel carrying the distinction (WCAG 1.4.1).

---

## State 01 — Actual

**Definition:** what is recorded, reconstructed from the reconciled ledger. No
prediction and no assumption appears in these figures.

### Composition

```
cash in hand          every account's opening balance + credits − debits
− restricted          lien-marked, pledged, FD-against-OD
− committed           obligations the owner has asked to ring-fence,
                      inside the 30-day commitment horizon
= available liquidity what is genuinely spendable today
+ overdraft headroom  reported SEPARATELY — it is credit, not cash
```

An unpaid invoice never enters any of these figures. This is asserted directly by
`tests/test_ledger_invariants.py::test_an_unpaid_invoice_is_never_counted_as_cash`.

### Evidence hierarchy

Every value carries an evidence class, and a value may be *demoted* freely but is
only ever *promoted* by an explicit, audited action:

| Rank | Class | Meaning |
|---:|---|---|
| 1 | `verified_actual` | Reconciled against a source document |
| 2 | `imported_actual` | From a feed, not yet verified |
| 3 | `owner_estimate` | Typed in by a human |
| 4 | `model_prediction` | Produced by a forecaster |
| 5 | `scenario_assumption` | A what-if input |
| 6 | `simulation_output` | Computed from (5) |

When an owner corrects a transaction's category, it becomes `verified_actual` and
the correction is appended to that row's transformation log — that is a promotion,
and it is audited.

### Data quality

```
score = 100 × (0.30·verified_share + 0.30·reconciled_share
             + 0.20·categorised_share + 0.20·freshness)
freshness = max(0, 1 − staleness_days / 14)
```

Reported on every screen that depends on it, with the specific warnings listed. A
forecast built on a stale ledger is a forecast built on fiction, and RUNWAY says so
rather than quietly degrading.

### Invariants

1. `opening + credits − debits = closing`, exactly, per account.
2. `Σ allocations(invoice) ≤ invoice.total`, always.
3. `Σ allocations(transaction) ≤ transaction.settleable` (gross for a gateway
   settlement).
4. `invoice.settled = Σ allocations(invoice)`, exactly.
5. No invoice is ever settled beyond its total.

`scripts/verify_ledger.py` runs all five across every account, invoice and
transaction — 4,996 checks on the demo workspace.

---

## State 02 — Predicted

**Definition:** an evidence-based estimate of the future built from the actual state.
It is not a verified financial fact.

### Construction

```
closing[w] = closing[w−1]
           + collections from open invoices predicted into week w
           + collections from sales not yet invoiced
           − payments on open purchase invoices due in week w
           − purchases supporting forecast sales (COGS, lead-shifted)
           − obligations due in week w
           − recurring operating costs
```

Invoice-level, obligation-level, simulated 4,000 times. See
`DIGITAL_TWIN_MATHEMATICS.md` for every distribution and
`MONTE_CARLO_METHODOLOGY.md` for the sampling scheme.

### Quantile convention, stated explicitly

For a **cash balance** distribution:

- **P10** — a pessimistic path. 10% of simulated futures are worse.
- **P50** — the median.
- **P90** — an optimistic path.

These are *simulation quantiles*, not confidence guarantees. The distinction matters:
a confidence interval makes a claim about a parameter; these make a claim about the
model's own output distribution. Whether that distribution matches reality is a
separate, measured question — answered in **State reconciliation** below.

### Prediction metadata

Every predicted state records: a state id and version, the actual state it was built
from, creation timestamp, horizon, model version, seed, path count, every assumption
(including where the correlation coefficient came from), the ledger fingerprint, and
the data-quality score at the time.

### Forecast immutability

A new forecast **supersedes**; it never replaces.

```
new verified data
  → actual state v(n+1)
  → predicted state v(m+1)
  → previous forecasts remain queryable
  → previously-stored forecast points are scored against the actual outcome
```

This is not archival tidiness. Scoring a forecast requires the forecast *as it was
made*. A system that overwrites its predictions can never honestly report accuracy,
which is exactly why so many products quote an accuracy figure from a slide.

---

## State 03 — Simulated

**Definition:** a hypothetical future produced by explicitly changing one or more
assumptions. It never modifies actual financial reality.

### Isolation, structurally

```python
def apply_scenario(baseline, kind, params, as_of):
    fi = baseline.copy()          # deepcopy, in exactly one place
    extras = HANDLERS[kind](fi, params, as_of)
    return fi, extras
```

The handlers receive a copy. **No handler has a database session.** There is no
import of a model, no session parameter, no path from the scenario engine to a
ledger table. Isolation is a property of the call graph, not a rule someone has to
remember.

`tests/test_three_state.py::test_a_scenario_never_writes_to_the_ledger` counts
transactions, invoices, allocations and total settled value before and after running
a ₹50 lakh simulated loan, and asserts every count is unchanged.

### Branching from a fixed baseline

A scenario pins `baseline_actual_state_id` and `baseline_predicted_state_id` at
creation. Re-running it uses **those**, not whatever is current.

```
Baseline (actual v5 + predicted v5)
  ├── A: accept the order, no advance
  ├── B: accept with 30% advance
  ├── C: accept with supplier credit
  └── D: accept and discount receivables
```

All four are comparable because all four share a baseline *and a seed*. A system
that silently re-baselined would make every recorded decision unauditable a month
later.

### Common random numbers

Baseline and scenario use the same seed, so the same draws of customer delay,
revenue multiplier and expense shock. The difference between them is therefore
attributable to the decision rather than to sampling noise. This is textbook
variance reduction, and it is what lets RUNWAY report a 0.3-week runway difference
and mean it.

---

## State reconciliation — the feedback loop

### A versus P: how accurate were we?

`reconcile_forecasts()` matches every stored forecast point whose target week has
passed against the cash position actually recorded for that week, then reports MAE,
RMSE, WAPE, bias and P10–P90 coverage **per horizon**.

Worked example from the demo workspace:

```
Forecast made 2026-08-15, 4-week horizon
  predicted P50  ₹11,82,000      P10 ₹4,10,000   P90 ₹21,40,000
  actual         ₹13,54,000
  error          −₹1,72,000  (under-predicted)
  inside band    yes
```

Measured results are in `EVALUATION_RESULTS.md` and shown in the product on the
Business State Centre. When nothing has matured, the product shows **nothing** and
explains why — it does not fall back to a plausible-sounding number.

### P versus S: how different is the decision?

The counterfactual table: minimum cash P50 and P10, closing cash, runway P50 and
P10, breach probability, negative-cash probability, VaR and CVaR — baseline against
scenario, with the direction of each labelled `improved` / `worse` / `unchanged`.

### S versus A: did the decision work?

When the owner marks a scenario **implemented**, RUNWAY records the decision — and
explicitly does not create any ledger entry. As real weeks elapse,
`/api/scenarios/{id}/evaluate` compares the simulated path against the cash
positions actually recorded, reporting MAE, band coverage and a plain statement of
whether the simulation tracked reality.

This closes the loop: reality → prediction → decision → reality.

---

## Where each state lives

| Table | Holds |
|---|---|
| `business_states` | Immutable header: type, version, as-of, lineage, fingerprint, data quality, status |
| `actual_snapshots` | Cash, restricted, committed, AR, AP, loans, working capital |
| `predicted_snapshots` | Series, assumptions, model version, seed, runway, VaR/CVaR |
| `simulated_snapshots` | Scenario parameters, outputs, **both** baseline pointers |
| `forecast_points` | Flattened weekly rows, later resolved against actuals |
| `payment_predictions` | Invoice-level predictions, later resolved against settlements |
| `state_comparisons` | Stored comparison metrics with their type |
| `scenario_decisions` | What the owner decided, and the realised outcome |

---

## How the interface preserves the distinction

- Every tile and every chart series carries a state badge.
- Every copilot answer states its state and renders a different disclaimer per state.
- Actual is solid; predicted carries its band; simulated is dashed.
- Scenario results always end with the isolation guarantee in plain words.
- The briefing labels each line with the state it came from.

A user should never have to wonder which of the three they are looking at.
