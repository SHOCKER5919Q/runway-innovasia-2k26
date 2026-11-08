# Counterfactual decision engine

## The question

"Should I accept this order?" is not a question about profit. It is a question about
whether the business can fund the gap between paying for the materials and being
paid for the goods. A profit calculation answers a different question and answers
it confidently, which is why so many profitable MSMEs run out of cash.

## Comparison

`app/financial_states/state_manager.py::compare_simulations`

Baseline and scenario are simulated under **common random numbers** and compared on
nine metrics, each labelled with whether the change is an improvement:

| Metric | Better when |
|---|---|
| Minimum cash P50 | Higher |
| Minimum cash P10 | Higher |
| Closing cash at horizon P50 | Higher |
| Runway P50 | Higher |
| Runway P10 | Higher |
| Probability of breaching the buffer | Lower |
| Probability of negative cash | Lower |
| Liquidity VaR (95%) | Lower |
| Liquidity CVaR (95%) | Lower |

Alongside: the scenario's own economics — expected revenue and profit, material
cost, advance, **funding gap in days**, financing cost, EMI, net advance.

## The signature comparison

₹15 lakh order, 18% margin, 60-day terms, demo workspace:

| Metric | Baseline | Accept as-is | Accept with 30% advance |
|---|---:|---:|---:|
| Minimum cash P50 | ₹11,07,339 | ₹2,10,926 | ₹6,23,924 |
| Minimum cash P10 | ₹20,341 | −₹11,03,917 | −₹6,44,189 |
| Runway P50 | 13.0 wk | 10.8 wk | 12.4 wk |
| Breach probability | 17% | **54%** | **35%** |
| Expected profit | — | ₹2,70,000 | ₹2,70,000 |
| Funding gap | — | 51 days | 51 days |

The profit is identical. The liquidity consequence is not. That difference is the
entire argument for simulating a decision rather than costing it.

## Optimisation

`app/digital_twin/decision_optimizer.py`

```
scale   = max(|Δliquidity|, |profit|, |Δdownside|, |cost|, 1)
utility = w_liq·Δliquidity/scale + w_profit·profit/scale
        − w_risk·Δdownside/scale − w_cost·cost/scale
```

Weights come from the business's declared risk appetite and are returned with the
result alongside every term.

### Policy constraints

An option is marked **infeasible** — with the breach named — when it:

- takes P10 cash negative,
- pushes breach probability past the configured ceiling (default 40%),
- carries a cost of credit above the business's maximum APR,
- produces an order margin below the business's minimum.

Infeasible options are still shown, still scored, and still ranked below feasible
ones. Hiding them would hide the reason.

### Worked ranking

```
Recommended: Discount receivables                 utility +0.400   feasible
             Working-capital loan                 utility +0.330   feasible
             Accept with 30% advance              utility −0.391   P10 cash goes negative
             Accept, no advance                   utility −0.455   P10 negative;
                                                                   breach 56% > 40% limit
```

Both ways of accepting the order breach policy; the two financing options do not.
That is a useful answer, and it is one a margin calculation cannot produce.

## What the engine refuses to do

**It does not decide.** The response carries an explicit caveat:

> The highest-utility option is not automatically the right business decision.
> Relationships, strategy and information not in the ledger are not modelled.
> RUNWAY ranks; the owner decides.

**It does not recommend borrowing on its own merits.** Financing appears only inside
a comparison where the cost of the facility sits beside the cost of the shortfall it
would cover, and only after the free options — collecting overdue receivables and
deferring discretionary purchases — have been listed with their own costs of zero.

**It does not promise availability.** Every financing option carries a statement
that RUNWAY does not arrange credit and cannot predict approval.

## Closing the loop

A scenario can be marked **implemented**, which records an intention and creates no
ledger entry. As weeks pass, `/api/scenarios/{id}/evaluate` compares the simulated
path against the cash positions actually recorded:

```
weeks elapsed    4
MAE              ₹1,84,000
band coverage    75%
lesson           The simulation tracked reality well.
```

Where coverage is poor the lesson reads: *"Reality diverged from the simulation.
Review which assumption was wrong before relying on a similar scenario again."*

This is the part most decision tools omit, and it is the only part that improves
anything over time.
