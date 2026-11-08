# Quantitative methods borrowed from financial markets

Mature market-risk technique adapted to MSME liquidity. For each: what it does in
its original setting, what the adaptation is, what it needs, what it assumes, where
it breaks, and whether it was worth it.

> **Standing caveat.** None of these are regulated measures. They are operational
> liquidity tools that happen to share mathematics with instruments that are
> regulated elsewhere. The product says so wherever a number appears.

---

## Value at Risk → liquidity VaR

**Originally:** the loss on a portfolio not exceeded with probability α over a
horizon.

**Adapted:** the *shortfall against the safety buffer* not exceeded with probability
α over 13 weeks.

```
loss^(p) = max(0, buffer − min_week_cash^(p))
VaR_95   = quantile_95(loss)
```

| | |
|---|---|
| **Inputs** | Simulated weekly cash paths, the safety buffer |
| **Assumes** | The simulation's distribution resembles reality — measured, not assumed, in `DIGITAL_TWIN_VALIDATION.md` |
| **Breaks when** | History does not contain the event being priced; a structural break occurs |
| **Benefit** | "The quarter could be ₹6.49 lakh short" is a sentence an owner can size a facility against |
| **Verdict** | **Kept.** Four lines of code, and it reframes the forecast as a planning input |

---

## Conditional VaR → liquidity CVaR

**Originally:** expected loss conditional on exceeding VaR.

**Adapted:** mean shortfall in the worst 5% of simulated quarters.

For a business deciding whether it can *survive* a shock, the tail is the question —
VaR says how bad a bad quarter looks, CVaR says how bad it gets when it goes bad.
CVaR is also coherent (sub-additive), which VaR is not, so it composes sensibly
across risks.

**Verdict: kept.** Demo: VaR ₹6.49 lakh, CVaR ₹13.67 lakh. The gap is the point.

---

## Monte Carlo simulation

**Originally:** pricing path-dependent derivatives.

**Adapted:** generating plausible cash trajectories from invoice-level uncertainty.

A single-number forecast gives an owner no way to distinguish "comfortable" from
"one late payment from missing payroll". The distribution is the product.

Fully vectorised: 4,000 paths × 14 weeks in ~50 ms, which is what makes the Scenario
Lab interactive rather than a batch job.

**Verdict: kept — it is the engine.** See `MONTE_CARLO_METHODOLOGY.md`.

---

## Gaussian copula → correlated payment delays

**Originally:** correlated defaults in a credit portfolio.

**Adapted:** a single market-wide factor shared by every customer on a path.

```
shock_i = 0.75·(√ρ·Z + √(1−ρ)·ε_c) + 0.25·η_i
```

**Why it is not optional:** independent delays understate the probability of a
*simultaneous* shortfall, which is exactly the event that kills businesses.

**Breaks when:** the dependence is not elliptical. Gaussian copulas famously
underestimate joint tail events — the 2008 lesson. For MSME payment timing, where
the tail is "several buyers pay late in the same month" rather than "everything
defaults at once", the approximation is defensible; for a solvency model it would
not be.

**Verdict: kept, with the limitation documented.** ρ is estimated from the business's
own data and the product reports when it found none.

---

## Common random numbers

**Originally:** variance reduction in simulation comparison.

**Adapted:** baseline and scenario share a seed, so the difference between them is
the decision rather than the noise.

Without it, comparing two scenarios at 2,500 paths carries ~±2% sampling noise on
the mean — the same order as the effect being measured.

**Verdict: kept, and arguably the highest value-per-line technique in the codebase.**
It is what makes a 0.3-week runway difference meaningful.

---

## Herfindahl-Hirschman Index

**Originally:** market concentration in antitrust; single-name risk in portfolios.

**Adapted:** counterparty, sector and region concentration of revenue.

```
HHI = Σ(share²)        effective counterparties = 1/HHI
```

The reciprocal is what makes it usable: "the equivalent of 4.9 equally-sized
customers carry this book" is actionable; "HHI 0.205" is not. Both are shown.

**Verdict: kept.**

---

## Sortino / downside deviation

**Originally:** risk-adjusted return penalising only downside volatility.

**Adapted:** the cash-flow stability health dimension counts only negative weeks.

```
downside_deviation = √( mean( min(0, weekly_net)² ) )
```

A business that occasionally has a very good week should not be marked unstable for
it. Standard deviation would do exactly that.

**Verdict: kept.**

---

## Robust statistics (median / MAD)

**Originally:** outlier-resistant estimation.

**Adapted:** anomaly detection within a transaction category.

```
robust z = (x − median) / (1.4826 · MAD)
```

Mean and standard deviation are dragged by the very outliers being sought, so a
single ₹11 lakh payment raises the threshold enough to hide the next one.

**Verdict: kept.**

---

## Stress testing

**Originally:** regulatory capital adequacy under prescribed scenarios.

**Adapted:** eight predefined shocks, each re-simulated under common random numbers.

Largest customer defaults · receivables 30 days later · receivables 15 days later ·
revenue −20% · costs +15% · festive demand fails · market-wide payment squeeze
(ρ = 0.75) · compound shock.

Each reports whether the business survives on its own cash, survives only with the
overdraft, or does not survive.

**Verdict: kept.** The "does not survive even with the overdraft" result is the most
actionable output in the risk centre.

---

## Conformal prediction

**Originally:** distribution-free prediction intervals with finite-sample coverage.

**Adapted:** calibrating the payment-delay model's quantile band.

**Measured effect: coverage 61% → 84%** against an 80% target. Without it the
published band is decoration.

**Verdict: kept — and it is the difference between a calibrated interval and a
decorative one.**

---

## Techniques evaluated and rejected

| Technique | Why not |
|---|---|
| **Mean-variance / portfolio optimisation** | Optimises *weights* under return covariance. RUNWAY has no weights — it has a cash path with hard timing constraints. The mathematics does not transfer; only the vocabulary does. |
| **GARCH volatility modelling** | Needs long high-frequency series. Weekly MSME cash flow over 18 months is ~78 observations with strong seasonality. The model would fit noise. |
| **Black-Scholes / real options** | Tempting for "the option to defer a purchase", but it needs a traded underlying and a volatility that means something. Deferring a purchase is modelled directly as a scenario, which is both simpler and interpretable. |
| **Credit scoring models (Altman Z, Merton)** | Built for listed firms with market data and audited balance sheets. Applying them to an MSME with eighteen months of bank data would produce a number with no validity, and labelling it a "score" would invite exactly the misreading the product exists to prevent. |
| **Copula tail dependence (t-copula)** | More faithful for joint extremes, but needs far more data to estimate the degrees of freedom than is available. Noted as a future addition in `ROADMAP.md`. |
| **Reinforcement learning for decisions** | No reward signal, no safe exploration policy, and no owner should accept "the policy learned it" as the reason to defer a supplier payment. |

---

## Libraries considered

| Library | Decision |
|---|---|
| **MAPIE** | Not used. Split conformal for one quantile model is ~15 lines, and showing the arithmetic in `payment_delay.py` is more valuable here than hiding it behind an import. |
| **Riskfolio-Lib** | Not used. Portfolio-weight optimisation under asset covariance; nothing transfers. |
| **PyPortfolioOpt** | Not used, same reason. |
| **ruptures** | Not used. The spend-shift detector tests a *known* window; `ruptures` finds *unknown* change points in long series. |
| **River** | Not used. Data arrives in batches, not a stream. |
| **SHAP** | Not used. Ablation gives the same shape of answer, deterministically and faster. |
| **scikit-learn** | **Used** — gradient boosting and isolation forest. |
| **NumPy / SciPy / pandas** | **Used** throughout. |

The general rule: a technique is implemented directly when the adaptation surface is
smaller than the library's. That keeps the quantitative core auditable — which, in a
product whose entire argument is that its numbers can be checked, is the point.
