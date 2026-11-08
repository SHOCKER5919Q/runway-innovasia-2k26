# Monte Carlo methodology

## Why simulate at all

A single-number cash forecast is worse than useless: it is confidently wrong, and it
gives an owner no way to distinguish "comfortable" from "one late payment away from
missing payroll". The distribution is the product.

## Uncertain inputs

| Variable | Distribution | Source of the parameters |
|---|---|---|
| Receivable payment date | `Normal(μ_i, σ_i)` truncated at ≥ 0 days, with a shared factor | μ from the payment-delay model, σ from its conformal band |
| Sales not yet invoiced | `LogNormal` around the weekly run-rate | CV from the business's own weekly history |
| Collection lag on those | `Normal(median lag, sd lag)` | Realised lags over the last 12 months |
| Operating costs | `LogNormal`, CV 12% | Trailing ledger |
| Unplanned expense | Poisson arrivals × Exponential severity | λ = 0.06/week, mean ₹60,000 |
| Supplier and statutory dates | `Normal(due, 0.5–2 days)` | Near-deterministic by nature |

Lognormals use `mean = −σ²/2` so the **mean** sits at the point estimate rather than
the median — otherwise every lognormal quietly biases the forecast upward.

## Correlation: a single-factor copula

```
Z      ~ N(0,1)              one draw per path — the market
ε_c    ~ N(0,1)              one per customer
η_i    ~ N(0,1)              one per invoice

shock_i = 0.75·( √ρ·Z + √(1−ρ)·ε_{c(i)} ) + 0.25·η_i
```

The 0.75/0.25 split separates *customer-level* behaviour from *invoice-level* noise:
a buyer has a habit, and individual invoices wobble around it.

**Why this is not optional.** Independent delays understate the probability of a
simultaneous shortfall, which is precisely the event that kills businesses. Setting
ρ = 0.6 in the sensitivity table shows what the assumption is worth.

**Estimating ρ:** pairwise Pearson correlation of monthly mean delay across
customers with ≥ 6 settled months. On the demo book this returns 0.025 — the
generator draws delays independently, and RUNWAY reports "payment delays are largely
independent across customers in this sample" rather than asserting a correlation it
did not find. When there is too little history, ρ = 0.25 with the reason recorded.

## Common random numbers

A scenario comparison re-uses the baseline's seed, so both paths see the same draws.

Without it, comparing two scenarios at 2,500 paths carries roughly ±2% of sampling
noise on the mean — which is the same order as the effect being measured. With it,
the difference is attributable to the decision. This is standard variance reduction
and it is what makes a 0.3-week runway difference meaningful rather than decorative.

## Vectorisation

All paths advance together as NumPy arrays. There is no Python loop over paths:

```python
inflow  = np.zeros((paths, W + 1))
days    = np.maximum(0, mu[None, :] + sg[None, :] * shock)   # (paths, invoices)
wi      = _week_index(days, as_of, W)
_scatter(inflow, wi, amounts, W)                              # masked add.at
```

4,000 paths × 14 weeks × ~215 invoices in **~50 ms**. That is what makes the
Scenario Lab feel like a slider rather than a batch job.

## Horizon handling

Flows landing past the horizon are **dropped and counted**, never clipped into the
final bucket:

```python
mask = (idx >= 0) & (idx <= n_weeks)
np.add.at(target, (rows[mask], idx[mask]), values[mask])
dropped = values[~mask].sum() / paths
```

Clipping produced a spurious ₹70 lakh jump in week 13 — the forecast appeared to
claim the business ended the quarter flush purely because the window closed. The
dropped amounts are reported under `beyond_horizon_paise` with a note.

The remaining asymmetry — purchases paid at ~42 days against collections at ~53 —
is not merely disclosed. Any scenario that changes the sales run-rate is **re-run
over 26 weeks** by `long_horizon_check()`, and both figures are returned:

```
revenue −20%:  closing cash −₹3,50,530 over 13 weeks
                             −₹7,47,749 over 26 weeks
               → "Most of the impact lands in the second quarter, because the
                  purchases are paid long before the collections they support
                  arrive. Judge this decision on the 26-week view."
```

Scenarios that only move money already owed — a payment delay, a customer default —
are not horizon-biased, so the check returns `None` rather than running a pointless
second simulation.

## Outputs

Per week: P10, P25, P50, P75, P90 and the mean of closing cash, plus median inflow,
outflow and net.

Across paths: minimum cash at P10/P50/P90, runway at P10/P50/P90, first breach week,
breach probability overall and per week, negative-cash probability, liquidity VaR
and CVaR at 95%, and expected shortfall.

Plus a driver breakdown — what is actually moving the number — each labelled with
whether it came from the ledger or from an estimate.

## Convergence and seeds

| Paths | Use | Monte Carlo error on the mean |
|---:|---|---|
| 300 | Catalogue smoke tests | ~6% |
| 1,000–1,500 | Sensitivity, stress tests | ~2.5% |
| 2,500 | Interactive scenario runs | ~2% |
| 4,000 | The stored forecast | ~1.5% |

Every run records its seed. The default (20260101) is configurable, and
`test_same_seed_gives_identical_results` asserts the guarantee.

## Validated properties

| Property | Test |
|---|---|
| Quantiles never cross at any week | `test_quantile_paths_are_ordered` |
| Bucket 0 is exactly today's balance | `test_bucket_zero_is_todays_balance` |
| Same seed ⇒ identical output | `test_same_seed_gives_identical_results` |
| Different seeds stay within 25% | `test_different_seeds_differ_but_stay_close` |
| **Paying earlier can only help** | `test_paying_earlier_can_only_help` |
| **Paying later can only hurt** | `test_paying_later_can_only_hurt` |
| CVaR ≥ VaR, always | `test_var_is_never_greater_than_cvar` |
| Nothing is silently dropped | `test_nothing_is_silently_dropped_at_the_horizon` |
| Probabilities are in [0,1] | `test_probability_fields_are_probabilities` |
| A revenue shock cannot improve closing cash | `test_committed_purchasing_is_not_cancelled_by_a_revenue_shock` |

The monotonicity tests are the valuable ones. They encode properties that *must*
hold for any correct implementation, and both of them caught real bugs — the week
anchoring and the horizon clipping — that no amount of eyeballing a chart would have
revealed.

## What this does not model

- **Regime change.** Parameters are estimated from history and held fixed. A
  structural break is invisible until it appears in the data.
- **Owner reaction.** Real owners chase collections when cash is tight. The model
  assumes passivity, which makes it conservative.
- **Correlation between revenue and delay.** In a downturn both worsen together.
  They are modelled independently today; this is the most defensible next addition.
- **Fat tails.** Payment delays are normal here. Reality has a longer right tail —
  the occasional buyer who takes 200 days.
