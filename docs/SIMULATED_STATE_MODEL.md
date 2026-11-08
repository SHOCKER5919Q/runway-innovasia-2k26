# Simulated state model

*Companion to `THREE_STATE_ARCHITECTURE.md`. The engine is documented in
`SCENARIO_ENGINE.md` and the decision comparison in
`COUNTERFACTUAL_DECISION_ENGINE.md`.*

## What it is

A hypothetical future produced by explicitly changing one or more assumptions about
the business. It never modifies actual financial reality.

## The isolation guarantee, and why it holds

```python
def apply_scenario(baseline: ForecastInputs, kind, params, as_of):
    fi = baseline.copy()          # deepcopy, in exactly one place
    extras = HANDLERS[kind](fi, params, as_of)
    return fi, extras
```

Three facts make this airtight rather than aspirational:

1. The copy happens in **one function**, not in each of twelve handlers.
2. **No handler receives a database session.** There is nothing to write with.
3. The handlers mutate a plain dataclass of scheduled inflows and outflows. That
   dataclass has no ORM mapping and no persistence path.

A simulated payment is therefore not a payment, and a simulated loan is not a
liability — not because the code is careful, but because there is no mechanism by
which it could be.

**Asserted by:** `test_a_scenario_never_writes_to_the_ledger` counts transactions,
invoices, allocations and total settled value before and after a ₹50 lakh simulated
loan. `test_applying_a_scenario_does_not_mutate_the_baseline_inputs` runs two
scenarios against the same inputs object and asserts it is byte-identical afterwards.

## Scenario record

```
Scenario
  name, kind, parameters_json
  baseline_actual_state_id        pinned at creation
  baseline_predicted_state_id     pinned at creation
  parent_scenario_id              for branches
  origin                          ui | copilot | preset
  last_run_state_id
```

The pinned baselines are what make a saved comparison stay honest. Re-running a
scenario a month later re-uses the state it was created against, so the numbers the
owner saw when they decided are the numbers that are still there.

## Outputs

```
SimulatedSnapshot
  scenario_id, baseline_actual_state_id, baseline_predicted_state_id
  parameters_json
  outputs_json         { scenario: full series, baseline: full series, economics }
  runway_weeks_p50, min_cash_p50, min_cash_p10
  peak_wc_requirement, breach_probability
  expected_profit, financing_cost, seed
```

Alongside the cash path, each handler returns its **economics** — the things the
cash curve alone does not show. For a new order that is the expected profit, the
material cost, the advance, the cash-out-before-cash-in, and the **funding gap in
days**, which is usually the figure that actually decides the question.

## From decision to outcome

```
draft → considering → implemented → (weeks pass) → evaluated
                   ↘ rejected
```

Marking a scenario **implemented** records an intention. It creates no ledger entry;
the API response says so explicitly. The realised outcome is measured later from
verified transactions by `/api/scenarios/{id}/evaluate`, which compares the simulated
path against the cash positions actually recorded and reports MAE, band coverage and
a plain statement of whether the simulation tracked reality.

## What a scenario will not do

- It will not defer an invoice owed to a micro or small supplier unless the owner
  explicitly turns off MSMED protection. Deferring those risks a 43B(h)
  disallowance, and the engine treats that as a constraint rather than a preference.
  Asserted by `test_msmed_protected_invoices_are_not_deferred_by_default`.
- It will not imply that financing is available. Every financing scenario returns a
  disclaimer that RUNWAY does not arrange credit and cannot predict approval.
- It will not assume a benefit it cannot evidence. A hiring scenario applies any
  revenue uplift at the owner's stated probability and only after a ramp period,
  because a new hire does not pay for themselves on day one.
