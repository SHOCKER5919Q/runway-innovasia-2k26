# Digital twin validation

How RUNWAY avoids creating a false sense of certainty — and how to check that it
has.

## The controls

| # | Control | Where |
|---|---|---|
| 1 | Verified facts separated from inferred values | `evidence` column on every value-bearing table |
| 2 | Actual separated from predicted | Different tables, different API routes, different visual treatment |
| 3 | Predicted separated from simulated | Different snapshot tables and state types |
| 4 | Source tracked for every input | `source_system`, `source_ref`, `import_batch_id`, `raw_json` |
| 5 | Scenario assumptions recorded | `parameters_json` on the scenario and the snapshot |
| 6 | Uncertainty shown wherever it exists | P10/P50/P90 bands, probabilities, confidence scores |
| 7 | Missing data highlighted | Operational state lists what is absent rather than imputing it |
| 8 | Stale information detected | Staleness in days, feeding the data-quality score |
| 9 | Audit trail preserved | `audit_log`, `twin_events`, `transform_log_json` |
| 10 | Owner can correct inputs | `PATCH /api/transactions/{id}`, logged as a promotion to verified |

## Data quality

```
score = 100 × (0.30·verified + 0.30·reconciled + 0.20·categorised + 0.20·fresh)
fresh = max(0, 1 − staleness_days / 14)
```

| Band | Score |
|---|---|
| Good | ≥ 80 |
| Adequate | 60–79 |
| Weak | < 60 |

Demo workspace: **97.8 / 100**, with two warnings listed (123 unreconciled
transactions, 5 uncategorised). The warnings are shown, not summarised away.

## Backtesting

`reconcile_forecasts()` resolves every stored forecast point whose target week has
passed against the cash position actually recorded for that week.

| Reported | Meaning |
|---|---|
| MAE | Mean absolute error in paise |
| RMSE | Penalises large misses |
| WAPE | Σ\|error\| / Σ\|actual\| — used instead of MAPE because a cash position can approach zero, where MAPE explodes |
| Bias | Mean signed error. Positive means RUNWAY predicted more cash than arrived |
| P10–P90 coverage | Share of outcomes inside the band. Target 80% |

### Measured (demo workspace, 7 Nov 2026)

| Horizon | n | MAE | WAPE | Coverage |
|---:|---:|---:|---:|---:|
| 1 wk | 4 | ₹3,11,578 | 19.8% | 100% |
| 2 wk | 4 | ₹3,56,506 | 21.2% | 100% |
| 3 wk | 4 | ₹8,95,115 | 62.2% | 100% |
| 4 wk | 3 | ₹5,72,567 | 48.0% | 100% |
| 7 wk | 2 | ₹10,23,346 | 120.9% | 50% |
| 8 wk | 2 | ₹14,06,829 | 176.0% | 50% |

Payment-date predictions: **285 resolved**, MAE **10.04 days**, P10–P90 coverage
**88%** against an 80% target.

**Reading these honestly:** short-horizon coverage is good. Long-horizon coverage is
below target *and measured on two observations*, which is not enough to conclude
anything from. The table shows `n` for exactly that reason, and the product's
interpretation text says so rather than quoting the number alone.

## The bug this process caught

The first historical backfill used each invoice's **current** outstanding balance.
Evaluating 15 August therefore saw only the invoices still unpaid in November — 3
instead of 104.

| | Before the fix | After |
|---|---|---|
| Open receivables seen at 2026-08-15 | 3 | 104 |
| 8-week bias | −₹17,49,870 | ≈ 0 |
| 1-week coverage | 0% | 100% |

The forecasts were wildly pessimistic and the backtest was measuring a model that
had never existed. The fix is `app/ledger/asof.py`, and it is the single most
important correctness change in the project.

**Any system that backtests must reconstruct the world as it was.** Most do not, and
their published accuracy is a measurement of a model nobody ever ran.

## Scenario validation

| Property | Test |
|---|---|
| No ledger write of any kind | `test_a_scenario_never_writes_to_the_ledger` |
| Baseline inputs unmutated | `test_applying_a_scenario_does_not_mutate_the_baseline_inputs` |
| Branches share a baseline and a seed | `test_branches_share_the_baseline_and_the_seed` |
| Every catalogue entry executes | `test_scenario_handlers_all_run` |
| Unknown kinds rejected | `test_an_unknown_scenario_kind_is_rejected` |
| MSMED protection respected | `test_msmed_protected_invoices_are_not_deferred_by_default` |

## Running the checks

```bash
./run.sh verify     # ~5,000 accounting invariants, outside pytest
./run.sh evaluate   # regenerate every published accuracy figure
./run.sh test       # 191 tests
```

## What validation cannot tell you

Backtesting measures how well the model reproduced the past under parameters
estimated from that past. It cannot detect a regime change, it cannot price an event
that has not happened before, and on a small sample it cannot distinguish a good
model from a lucky one. The coverage tables carry their `n` so that last point is
visible rather than implied.
