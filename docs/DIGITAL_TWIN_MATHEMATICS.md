# Digital twin mathematics

Every formula RUNWAY uses, with its assumptions, its limitations and a worked
example. Nothing here is aspirational — each one is in the code at the path given.

---

## 1. Available liquidity

**`app/analytics/cash.py`**

```
cash_t           = Σ_accounts ( opening + Σ credits≤t − Σ debits≤t )
restricted_t     = Σ_accounts min(restricted, max(0, closing))
committed_t      = Σ obligations with reserve_cash, due in (t, t+30]
available_t      = cash_t − restricted_t − committed_t
od_headroom_t    = Σ limits − Σ max(0, −closing)
```

*Assumption:* restricted balances are correctly marked by the owner.
*Limitation:* the 30-day commitment horizon is a policy choice, not a derivation.

**Worked example (demo, 7 Nov 2026):**

```
cash            ₹14,07,195   (current ₹7,41,254 + cash ₹82,745 + FD ₹5,83,195)
− restricted     ₹5,00,000   (FD lien-marked against the overdraft)
− committed      ₹4,29,974   (GST ₹2,69,974 + payroll ₹1,60,000)
= available      ₹4,77,221
+ OD headroom   ₹15,00,000   reported separately — credit, not cash
```

The headline figure is **₹4.77 lakh**, not ₹14.07 lakh. The difference is the whole
point.

---

## 2. Weekly cash recursion

**`app/forecast/cashflow.py`, `app/forecast/monte_carlo.py`**

```
closing[0] = available cash today (excluding restricted)

closing[w] = closing[w−1]
           + Σ_i  A_i · 1[week(T_i) = w]          open receivables
           + Σ_k  R_k · 1[week(k·7 + L_k) = w]    sales not yet invoiced
           − Σ_j  B_j · 1[week(D_j) = w]          open payables
           − Σ_k  C_k · 1[week(P_k) = w]          purchases for those sales
           − Σ_o  O_o · 1[week(E_o) = w]          obligations
           − X_w                                   recurring opex
```

**Bucket convention.** Bucket 0 is *today* and holds the opening balance, no flows.
Bucket `w` covers days `[(w−1)·7, w·7)` from today and is labelled by the date
`as_of + w·7` — the balance at the *end* of that week.

This is anchored on `as_of`, not on the calendar Monday, and that detail is not
cosmetic. With a Monday anchor every payment arriving in the remainder of the
current week lands in bucket 0 and is discarded, which made "customers pay 7 days
earlier" register as **destroying ₹1.88 lakh** of cash. The sensitivity table caught
it; the anchor was changed.

**Horizon handling.** Flows landing past the horizon are **dropped and counted**,
never clipped into the final bucket. Clipping produced a spurious ₹70 lakh jump in
week 13. The dropped totals are reported under `beyond_horizon_paise`.

---

## 3. Receivable payment date, with correlation

**`app/forecast/monte_carlo.py`**

```
Z     ~ N(0,1)                   one market-wide factor, per simulated path
ε_c   ~ N(0,1)                   per customer
η_i   ~ N(0,1)                   per invoice

shock_i = 0.75·(√ρ·Z + √(1−ρ)·ε_{c(i)}) + 0.25·η_i
T_i     = max(0, μ_i + σ_i · shock_i)
```

`μ_i` is the predicted days-from-today for invoice *i*; `σ_i` is its conformally
calibrated spread, `(P90 − P10)/2.5631`.

**Why 2.5631:** for a normal distribution the 10th and 90th percentiles sit at
±1.2816σ, so the P10–P90 width is 2.5631σ.

**Why the common factor:** treating delays as independent is the classic
understatement of liquidity risk. When the market is tight, everybody pays late at
once. This is a single-factor Gaussian copula — the same device used for correlated
defaults in credit portfolios.

**Estimating ρ:** pairwise Pearson correlation of monthly mean delay across
customers with at least six settled months. Where there is too little history,
ρ = 0.25 with the reason recorded in the output. On the demo book the estimate is
0.025 — the generator draws delays independently, and RUNWAY correctly reports that
it found no correlation rather than asserting one.

---

## 4. Sales not yet invoiced

```
w_t         = weekly billed total, last 26 weeks (current partial week dropped)
d_t         = w_t / seasonality[month(t)]            de-seasonalise
base        = median(d_{t-11..t})
trend       = clip( median(d_{t-3..t}) / median(d_{t-11..t-4}), 0.80, 1.20 )
R_k         = base × seasonality[month(k)] × (1 + (trend − 1)·e^(−k/8))
```

**Why damped:** a four-week trend extrapolated thirteen weeks is an artefact, not a
forecast. The exponential decay returns the projection to the de-seasonalised base
over roughly eight weeks.

**Realised volume per path:** `R̃_k = R_k · LogNormal(−σ²/2, σ)` with
`σ = √(ln(1 + CV²))` and CV measured from the business's own weekly history. The
`−σ²/2` term keeps the lognormal's *mean* at `R_k` rather than its median.

---

## 5. Committed purchasing

```
C = round( (cogs_lead_days + supplier_credit_days) / 7 )

commitment(k) = 1                            for k < C
              = max(0, 1 − (k − C + 1)/C)    for k ≥ C      (linear taper)

purchase_k = max( R̃_k , R_k^baseline · commitment(k) ) × cogs_ratio
```

**Why this exists.** Without it, a 20% revenue shock came out as a cash
*improvement* of ₹3.5 lakh, because the model let the business stop buying on the
day demand fell. Real purchasing is committed: materials for the next few weeks are
ordered, in transit, or under a minimum-order commitment. After the fix, closing
cash falls monotonically with the depth of the shock (−₹0.75L at −10%, −₹3.14L at
−20%, −₹6.45L at −30%), which is both correct and what an owner needs to see.

---

## 6. Runway, with censoring

```
runway = w* + (closing[w*−1] − buffer) / (closing[w*−1] − closing[w*])
         where w* is the first week with closing[w] < buffer
       = horizon, if no such week exists          ← CENSORED
```

The linear interpolation gives sub-week resolution. The censoring is reported
explicitly: a runway equal to the horizon means "beyond the forecast window", and
the API returns a `censored` flag so the interface can say that instead of printing
"13.0 weeks" as though it were a measurement.

---

## 7. Liquidity VaR and CVaR

```
min_cash^(p)  = min over weeks 1..W of closing^(p)[w]      for each path p
loss^(p)      = max(0, buffer − min_cash^(p))
VaR_α         = quantile_α( loss )
CVaR_α        = mean( loss | loss ≥ VaR_α )
```

**The adaptation.** Market VaR asks "how much could this portfolio lose?". The
MSME question is "how far below my safety buffer could I fall?". The loss variable
is therefore a *shortfall against a threshold*, not a return.

**Stated plainly in the output:** this is an operational liquidity measure adapted
from market-risk VaR. It is not a regulated investment VaR and carries no
regulatory meaning.

**Why CVaR matters more here.** VaR says how bad a bad quarter looks. CVaR says how
bad it gets *when* it goes bad, and for a business deciding whether it can survive a
shock, the tail is the question.

---

## 8. Financial health score

```
score = Σ_d w_d · s_d          Σ w_d = 1,   s_d ∈ [0,100]
```

| Dimension | w | Inputs |
|---|---:|---|
| Liquidity | 0.20 | Runway P50 vs target; current ratio |
| Receivables quality | 0.16 | Overdue share; exposure-weighted delay; 60+ share |
| Cash-flow stability | 0.14 | Weekly CV; downside deviation (Sortino-style) |
| Debt service | 0.12 | Accrual DSCR |
| Customer concentration | 0.10 | Top-1 share vs policy; HHI |
| Revenue consistency | 0.10 | Monthly CV; 3-month vs prior-3 growth |
| Working-capital efficiency | 0.10 | DSO − DPO |
| Obligation coverage | 0.08 | (liquidity + expected collections) / obligations |

Each `s_d` is a piecewise-linear map anchored on values that mean something
operationally — "eight weeks of runway", not an arbitrary z-score.

**Two choices worth defending:**

*Downside deviation, not variance.* `√(mean(min(0, x)²))` over weekly net flow.
Upside volatility is not instability; a business that occasionally has a very good
week should not be penalised for it. Borrowed from the Sortino ratio.

*Accrual DSCR, not cash DSCR.* Monthly operating surplus is
`(sales taxable − purchase taxable − opex) / months`, not net bank movement. A
seasonal business can post a strongly negative cash month purely because it funded
working capital; a DSCR built on that reads 0.00× for a perfectly solvent company.
Lenders assess coverage on earnings, so RUNWAY does too.

**This is not a credit score.** Not issued by a bureau, no regulatory standing, and
the disclaimer travels with the number into the API, the UI and the shared report.

---

## 9. Concentration

```
HHI = Σ_i (v_i / Σv)²            effective counterparties = 1 / HHI
```

| HHI | Reading |
|---|---|
| < 0.15 | Unconcentrated |
| 0.15 – 0.25 | Moderate |
| > 0.25 | High |

**Demo:** HHI 0.205 (moderate), effective n = 4.9, top-1 share 29%, top-3 70%.
The interface leads with "the equivalent of 4.9 equally-sized customers carry this
book", because that is a sentence an owner can act on. The index is shown beside it.

---

## 10. Customer reliability

```
punctual   = max(0, 1 − max(0, mean_delay) / 45)
consistent = max(0, 1 − sd_delay / 30)
reliability = 100 × (0.55·punctual + 0.25·consistent + 0.20·(1 − overdue_share))
```

Computed from **settled invoices only**. Including open invoices would bias every
statistic optimistically, because the invoices that have not been paid yet are
exactly the ones that are late.

Data confidence is `min(1, n/12)` and is reported beside the score, so a customer
with three settled invoices is not presented with the same authority as one with
two hundred.

---

## 11. Robust anomaly detection

```
robust z = (x − median) / (1.4826 × MAD)        MAD = median(|x − median|)
```

Median/MAD rather than mean/sd, because the mean and standard deviation are dragged
by exactly the outliers being looked for. The 1.4826 makes MAD a consistent
estimator of σ for normal data. Threshold 4.0; above 6.0 is a warning.

**Spend change-point:**

```
t = (mean(last 6 weeks) − mean(baseline)) / (sd(baseline) / √6)
flag if |shift| ≥ 35% and |t| ≥ 2.5
```

**Duplicate payment:** same counterparty, same amount, ≤ 7 days apart, and **no
distinguishing bank reference**. The last condition is what keeps the false-positive
rate usable — a business genuinely does pay the same supplier the same amount twice.

---

## 12. Early-payment discount

```
annualised cost of forgoing = ( d / (1 − d) ) × ( 365 / days_saved )
```

Taking a 2% discount 20 days early on 30-day terms:

```
(0.02 / 0.98) × (365 / 10) = 74.5% annualised
```

Against a 24% borrowing-cost ceiling, that is worth borrowing to take — provided the
forecast says the cash is genuinely spare that week, which the Scenario Lab answers.

---

## 13. MSMED and 43B(h) scheduling

```
statutory_deadline = issue_date + min(agreed_credit_days,
                                      45 if written agreement else 15)
                     only when supplier.msme_class ∈ {micro, small}

effective_due      = min(contractual_due_date, statutory_deadline)
```

The forecast schedules payables at the **effective** due date, so a protected
invoice shows up in the week the law requires rather than the week the contract
prefers. The scenario engine refuses to defer those invoices unless the owner
explicitly overrides the protection.

---

## 14. Decision utility

```
scale   = max(|Δliquidity|, |profit|, |Δdownside|, |cost|, 1)
utility = w_liq·Δliquidity/scale + w_profit·profit/scale
        − w_risk·Δdownside/scale − w_cost·cost/scale
```

| Appetite | w_liq | w_profit | w_risk | w_cost |
|---|---:|---:|---:|---:|
| Conservative | 0.30 | 0.15 | 0.45 | 0.10 |
| Balanced | 0.30 | 0.30 | 0.28 | 0.12 |
| Aggressive | 0.20 | 0.48 | 0.18 | 0.14 |

Normalisation by a common scale keeps the four terms commensurable. Weights and
every term are returned with the result.

**The engine ranks; it does not decide.** The response carries an explicit caveat
that relationships, strategy and information outside the ledger are not modelled.

---

## 15. Exact money

Every amount is an integer number of paise. Proportional splits use the
largest-remainder method:

```
raw_i    = total · w_i / Σw
floor_i  = ⌊raw_i⌋
remainder = total − Σ floor_i
distribute the remainder one paisa at a time, largest fractional part first
⟹ Σ parts = total, exactly
```

This is why `opening + credits − debits = closing` holds exactly across 4,996
checks rather than approximately.
