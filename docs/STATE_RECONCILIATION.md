# State reconciliation

*Detail page for `THREE_STATE_ARCHITECTURE.md`.*

Three comparisons close three loops. Together they are what lets RUNWAY claim a
track record instead of a confidence.

---

## Actual vs Predicted — "how accurate were we?"

`app/financial_states/state_manager.py::reconcile_forecasts`

### Resolution

```python
for point in forecast_points where target_week_start <= today and actual is null:
    actual = cash_position(business, point.target_week_start)
    point.actual_paise = actual.cash − actual.restricted
    point.resolved_at  = now()
```

The actual is recomputed **as of the target week**, using point-in-time
reconstruction. Using today's balances would compare a forecast for August against
November's reality.

### Metrics, per horizon

| | Definition | Why this one |
|---|---|---|
| MAE | mean \|predicted − actual\| | Interpretable in rupees |
| RMSE | √mean(error²) | Penalises large misses |
| WAPE | Σ\|error\| / Σ\|actual\| | **Used instead of MAPE** — a cash position can approach zero, where MAPE explodes to meaningless magnitudes |
| Bias | mean(predicted − actual) | Positive means RUNWAY predicted more cash than arrived |
| Coverage | share inside P10–P90 | Target 80%. Below, the band is too narrow; well above, too wide |

### Worked example

```
Forecast made 2026-08-15, 4-week horizon, target week 2026-09-12
  P10 ₹4,10,000   P50 ₹11,82,000   P90 ₹21,40,000
  actual          ₹13,54,000
  error           −₹1,72,000   (under-predicted)
  inside band     yes
```

### Measured (demo workspace)

| Horizon | n | MAE | WAPE | Bias | Coverage |
|---:|---:|---:|---:|---:|---:|
| 1 wk | 4 | ₹3,11,578 | 19.8% | +₹2,44,997 | 100% |
| 2 wk | 4 | ₹3,56,506 | 21.2% | +₹3,56,506 | 100% |
| 4 wk | 3 | ₹5,72,567 | 48.0% | +₹5,72,567 | 100% |
| 8 wk | 2 | ₹14,06,829 | 176.0% | +₹10,90,995 | 50% |

Payment-date predictions: **285 resolved**, MAE **10.04 days**, coverage **88%**.

The product's own interpretation text reads:

> At horizons up to 4 weeks the P10–P90 band contained the actual outcome 100% of
> the time against an 80% target. Beyond 6 weeks coverage falls to 50% over only 4
> observations, so the long-horizon band is both less reliable and too thinly
> measured to draw a conclusion from.

### Retraining discipline

A single resolved prediction **does not** trigger retraining. The model is refit on
every forecast run from the full chronological history, with the same split, the
same calibration and the same significance guard. Chasing one event would be
overfitting with extra steps.

---

## Predicted vs Simulated — "how different is the decision?"

`compare_simulations()` returns nine metrics, each labelled `improved` / `worse` /
`unchanged`, plus the scenario's own economics. Detail and a worked example in
`COUNTERFACTUAL_DECISION_ENGINE.md`.

The method line travels with every comparison:

> Both paths simulated with the same seed and therefore the same random draws
> (common random numbers), so the difference is attributable to the decision rather
> than to simulation noise.

---

## Simulated vs Actual — "did the decision work?"

```
GET /api/scenarios/{id}/evaluate
```

Available only when the owner has marked the scenario **implemented**. Compares the
simulated path week by week against the cash positions actually recorded:

```json
{
  "available": true,
  "weeks_elapsed": 4,
  "rows": [
    {"week_start": "2026-11-09", "simulated_p50": "₹9,80,000",
     "actual": "₹10,42,000", "error": "₹62,000", "within_band": true}
  ],
  "mae": "₹1,84,000",
  "band_coverage": 0.75,
  "lesson": "The simulation tracked reality well."
}
```

Where coverage is poor the lesson reads:

> Reality diverged from the simulation. Review which assumption was wrong before
> relying on a similar scenario again.

### What marking "implemented" does not do

It records an **intention**. It creates no transaction, no invoice and no
obligation. The API response says so explicitly:

> Recorded as a decision only. No ledger entry was created — the outcome will be
> measured from verified transactions.

Asserted by
`tests/test_workflow_e2e.py::test_12_a_decision_can_be_recorded_without_touching_the_ledger`,
which checks that cash is unchanged across the call.

---

## When there is nothing to report

A freshly seeded workspace has no matured forecasts. The product returns:

> No forecast has reached its target week yet, so there is nothing to score. RUNWAY
> will not quote an accuracy figure it has not measured.

The demo workspace avoids this by backfilling genuine forecast runs at four past
dates during seeding — each a real forecast made from the ledger as it stood on that
date, which is exactly what the accuracy report needs.
