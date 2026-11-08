# ML methodology

## The claim this document has to support

RUNWAY publishes accuracy figures. This document explains how they are produced, so
that someone sceptical can check them — and `./run.sh evaluate` regenerates every
one.

---

## 1. Payment-delay prediction

### Target

`delay = settled_date − due_date`, in days, for invoices that have **actually been
settled**. Negative means early.

### Features — and the leakage problem

The single most common way to get a convincing-but-useless payment-delay model is to
build customer features from the whole dataset. A customer's "average delay" then
contains information from invoices settled *after* the one being predicted. The test
score looks excellent and the live model is worthless.

`app/forecast/features.py` makes one strict chronological pass. When invoice *i* is
featurised, only invoices both **issued and settled** strictly before *i*'s issue
date are visible.

```python
for inv in sales_sorted_by_issue_date:
    while settlement_events[idx].date < inv.issue_date:
        absorb(settlement_events[idx])      # now, and only now, it is knowable
        idx += 1
    x = featurise(inv, history_so_far)
```

**Asserted, not assumed.** `tests/test_no_leakage.py` recomputes the features with
every settlement after a cut-off hidden and requires the earlier invoices' feature
vectors to be **byte-identical**. If any feature peeked at the future, that test
fails.

### The 21 features

| Group | Features |
|---|---|
| Invoice | credit days, log amount, amount relative to the customer's historical mean |
| Customer history | prior settled count, mean / median / sd of delay, last-3 mean, last-6 mean, **delay trend per month**, on-time rate, partial-payment rate, tenure |
| Exposure | open exposure relative to this invoice's size |
| Seasonality | due-month sine and cosine, month-end flag, due weekday, quarter-end flag |
| Context | global prior mean delay, months since the book began |

`cust_delay_trend_per_month` — the OLS slope over the customer's last ten settled
delays — is the feature a flat average structurally cannot provide. A buyer drifting
from 8 days late to 22 days late over a year looks identical to a steady 15-day
payer in the mean.

### Models

| | |
|---|---|
| **B0** | Global median delay. The free baseline. |
| **B1** | Per-customer expanding median. The strong, cheap baseline — what a spreadsheet would do. |
| **M** | Gradient-boosted regression: quantile loss at α = 0.1 / 0.5 / 0.9, plus an L1 (absolute-error) model for the median. 300 trees, depth 3, lr 0.05, subsample 0.9, min leaf 12. |

Gradient boosting over a neural model because the dataset is hundreds to a few
thousand invoices, the relationships are near-monotone, and per-feature behaviour
can be probed by ablation.

### Split

**Chronological. No shuffling anywhere.**

```
|------------- train 60% -------------|--- calibration 20% ---|--- test 20% ---|
                                   by issue date →
```

A random split on time-ordered financial data trains on the future and tests on the
past.

### Stacking and the selection guard

The median prediction is a blend:

```
p50 = w · GBM + (1 − w) · per-customer median
```

`w` is fitted on the calibration slice by grid search. Then — and this is the part
that matters — the blend only ships if it clears a **paired significance test**:

```python
diff = |baseline_error| − |stacked_error|     # per invoice, same invoices
t    = mean(diff) / (sd(diff) / √n)
ship = (t ≥ 1.96) and (relative gain ≥ 2%)
```

The two predictors score the *same* invoices, so the correct test is on the
per-invoice difference in absolute error, not on the two error distributions
separately.

**On the demo book the model loses this test.**

```
paired calibration test over 166 invoices:
  baseline MAE 8.87d, stacked 8.59d at w=0.85 (+3.2%, t=+1.29).
  Learned model NOT shipped — the improvement is not distinguishable from noise
  (needs t ≥ 1.96 and ≥ 2% gain), so RUNWAY uses the per-customer median.
```

That sentence is returned by the API, rendered on the Cash Runway screen, and
printed by the evaluation script.

**Why this is the right outcome.** The synthetic generator draws each customer's
delay from a stable distribution with structure the GBM can partly learn (size
effects, seasonality, drift) — but the irreducible noise, σ ≈ 7–11 days, dominates.
The per-customer median is close to Bayes-optimal under those conditions, and a 3%
gain on 166 invoices is noise. On a real book with stronger drift and richer
features the stack would likely ship; the mechanism works either way, and it is the
mechanism that is the deliverable.

### Conformal calibration

Quantile regression is not calibrated out of the box. Split conformal fixes it on a
held-out slice:

```
nonconformity_i = max( (q50 − y_i)/(q50 − q10), (y_i − q50)/(q90 − q50) )
scale           = the ⌈(n+1)·0.80⌉-th smallest nonconformity
q10' = q50 − (q50 − q10)·scale
q90' = q50 + (q90 − q50)·scale
```

**Measured effect on the demo book: P10–P90 coverage 61% → 84%** against an 80%
target. Without this step "P10–P90" is decoration.

After scaling, the three quantiles are re-sorted so they can never cross — a
quantile forest can produce p10 > p90 locally, and every downstream interval would
inherit the nonsense.

### Converting a delay to a probability

```
σ_implied = (p90 − p10) / 2.5631           (the normal P10–P90 width)
P(paid within d days) = Φ( (d − p50) / σ_implied )
```

Monotone in `d` by construction, and asserted.

### Re-anchoring an overdue invoice

If an invoice's predicted date has already passed, the **whole distribution** is
shifted — not just the median. Shifting the median alone makes the quantiles cross,
and every interval downstream becomes nonsense. This was a real bug, caught by
`test_quantile_paths_are_ordered`.

### Explainability

Per-feature contribution by **single-feature ablation** against the training mean:

```
base = predict(mean_vector)
contribution_j = predict(mean_vector with feature j set to this invoice's value) − base
```

Model-agnostic, deterministic, cheap, and the same shape of answer SHAP gives.
Shown on the receivables detail as "+4.5 days from recent payment behaviour".

### Measured results

| Metric | Sri Lakshmi | Deccan Precision |
|---|---:|---:|
| Test MAE (shipped predictor) | 10.06 d | 11.87 d |
| Baseline: per-customer median | 10.06 d | 11.87 d |
| Baseline: global median | 11.92 d | 13.41 d |
| Conformal P10–P90 coverage | 84% | 78% |
| Late-alert (>15 d) precision / recall | 0.68 / 0.64 | 0.67 / 0.89 |
| Resolved predictions, realised MAE | 10.04 d (n=285) | 12.23 d (n=292) |
| Resolved coverage | 88% | 72% |

---

## 2. Cash-flow forecasting

Not a learned model, and deliberately so. See `PREDICTED_STATE_MODEL.md` for the
argument and `DIGITAL_TWIN_MATHEMATICS.md` for the recursion.

Statistical estimation is confined to the genuinely unknown component — sales not
yet invoiced — where it is a robust de-seasonalised median with a damped trend.
That choice is defensible precisely because the component is small relative to the
known invoices and obligations, and because the method is auditable in four lines.

### Backtest

Stored `forecast_points` are resolved against the cash position recorded for their
target week. Metrics per horizon: MAE, RMSE, WAPE, bias, P10–P90 coverage.

WAPE rather than MAPE because a cash position can approach zero, where MAPE explodes
to meaningless magnitudes.

| Horizon | n | WAPE | Coverage |
|---:|---:|---:|---:|
| 1 wk | 4 | 19.8% | 100% |
| 2 wk | 4 | 21.2% | 100% |
| 4 wk | 3 | 48.0% | 100% |
| 8 wk | 2 | 176.0% | 50% |

Long horizons are poor **and measured on two observations**. The table carries `n`
so that is visible, and the product's interpretation text says it rather than
quoting the number alone.

---

## 3. Anomaly detection

Primary detectors are interpretable by requirement, not by preference. An
unexplainable alert about someone's money destroys trust faster than a missed one.

| Detector | Method | Why |
|---|---|---|
| Amount outlier | Robust z via median/MAD, threshold 4.0 | Mean/sd are dragged by the outliers being sought |
| Duplicate payment | Same counterparty, same amount, ≤ 7 days, no distinguishing reference | The reference condition is what keeps false positives usable |
| Spend shift | Two-sample t on a 6-week window, \|shift\| ≥ 35% and \|t\| ≥ 2.5 | Catches drift no single transaction reveals |
| Isolation Forest | 200 trees, 1% contamination | **Cross-check only, reported as information** — it cannot explain itself |

---

## 4. What would change on real data

1. The learned payment-delay model would probably ship. Real books carry stronger
   drift, buyer-specific seasonality and process effects (approval cycles, invoice
   disputes) that a median cannot represent.
2. Richer features become available: GST filing behaviour, buyer credit signals,
   dispute and credit-note history, sector indices.
3. Correlation estimates become meaningful. The demo generator draws delays
   independently, so ρ ≈ 0.025 is correct and uninteresting; real books cluster.
4. Fat tails matter. Normal delays understate the buyer who takes 200 days.
5. Longer history makes long-horizon coverage measurable rather than merely
   reported.

---

## 5. Reproducing everything

```bash
./run.sh evaluate          # regenerates docs/EVALUATION_RESULTS.md
./run.sh test              # includes the leakage and calibration tests
```

Every figure in this document comes from that script. None is quoted from memory,
and none appears in the product that the script cannot regenerate.
