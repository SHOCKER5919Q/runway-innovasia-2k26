# Scenario engine

## The design decision

A scenario is a **named, parameterised mutation of `ForecastInputs`**. That single
choice gives three properties for free:

1. **Isolation is structural.** `apply_scenario` deep-copies the baseline in one
   place and hands the copy to a handler that has no database session. There is no
   path from a scenario to a ledger table.
2. **Comparability is guaranteed.** Baseline and scenario are evaluated by the same
   simulator on the same object type, differing only in the mutation.
3. **Reproducibility is free.** Same baseline + same parameters + same seed ⇒
   identical output.

```python
def apply_scenario(baseline, kind, params, as_of) -> (ForecastInputs, dict):
    fi = baseline.copy()
    extras = HANDLERS[kind](fi, params, as_of)
    return fi, extras
```

## The twelve scenarios

| Kind | Question it answers |
|---|---|
| `new_order` | Can I afford to take this order? |
| `payment_delay` | What if my biggest customer pays 30 days late? |
| `customer_default` | What if they stop paying altogether? |
| `revenue_shock` | What happens if revenue drops 20%? |
| `cost_increase` | What if raw material prices go up? |
| `hiring` | Can I afford two more people? |
| `equipment_purchase` | Should I buy this machine now? |
| `financing` | What does borrowing actually cost me? |
| `invoice_discounting` | Should I discount receivables instead of borrowing? |
| `supplier_terms` | What if my suppliers give me more time? |
| `defer_purchase` | How much does waiting help? |
| `one_off_expense` | Can I absorb a sudden bill? |

Plus `composite`, which chains any of the above.

---

## `new_order` — the signature scenario

This is the one that demonstrates why a cash model beats a profit calculation.

```
advance_amount  = order_value × advance_pct                 day: start_in
material_cost   = order_value × material_share              day: start_in + supplier_credit
delivery        = start_in + production_days
balance         = order_value − advance_amount              day: delivery + credit_days

funding_gap_days = (delivery + credit_days) − (start_in + supplier_credit)
peak_need        = max(0, material_cost − advance_amount)
```

**Worked example** — ₹15 lakh at 18% margin, no advance, 60-day terms:

```
day  7   order starts
day 37   ₹12,30,000 of materials payable          ← cash out
day 28   goods delivered
day 88   ₹15,00,000 balance collected             ← cash in

funding gap    51 days
peak need      ₹12,30,000
expected profit ₹2,70,000
```

The order is profitable. The question is whether the business can **fund 51 days of
₹12.3 lakh**, and the answer in the demo workspace is that minimum cash falls from
₹11.07L to ₹1.79L and the chance of breaching the safety buffer rises from 17% to
55%.

Change the advance to 30% and the same order becomes safe: minimum cash ₹6.24L,
breach probability 35%. Same order. Same margin. Different financing.

---

## `hiring` — modelling an uncertain benefit honestly

Cost is certain and immediate. Benefit is uncertain and delayed. Most tools model
the first and assume the second.

```
cost_month        = headcount × monthly_cost_per_head        from start_in, monthly
uplift_recognised = expected_monthly_uplift × uplift_probability
                    recognised only from month ≥ ramp_months
                    collected after the business's own median collection lag
```

The probability and the ramp are both owner inputs with conservative defaults (50%,
3 months). The output reports `risk_adjusted_uplift_paise` separately from the cost,
so the owner can see exactly how much of the case rests on a hope.

---

## `financing` and `invoice_discounting` — the cost of money

```
financing:
  fee          = amount × processing_fee_pct
  emi          = amortised(amount, annual_rate, tenure_months)
  net received = amount − fee                         at draw_in
  total cost   = emi × tenure − amount + fee

invoice discounting, per invoice:
  advance      = outstanding × advance_pct
  interest     = advance × annual_rate × days_to_due / 365
  platform fee = outstanding × platform_fee_pct
  net now      = advance − interest − fee
  retention    = outstanding − advance, released after the buyer settles
```

Discounting selects the **slowest-paying** invoices first, because that is where the
financing cost buys the most time.

Both return a disclaimer in the payload: RUNWAY does not arrange credit and cannot
predict whether any lender or platform will approve. No scenario implies
availability.

---

## `supplier_terms` — a constraint the engine will not cross

```
for each open supplier invoice:
    if respect_msmed and the invoice is protected:   skip
    else:                                            day_offset += extra_days
```

An invoice is protected when the supplier is a registered micro or small enterprise.
Deferring those past the MSMED window risks a 43B(h) disallowance, so the engine
treats it as a constraint rather than a preference. Turning the protection off is
possible and returns an explicit warning in the narrative.

Asserted by `tests/test_three_state.py::test_msmed_protected_invoices_are_not_deferred_by_default`.

---

## Composite scenarios

```json
{
  "kind": "composite",
  "params": {"steps": [
    {"kind": "revenue_shock",  "params": {"drop_pct": 0.20}},
    {"kind": "cost_increase",  "params": {"increase_pct": 0.15, "scope": "both"}},
    {"kind": "payment_delay",  "params": {"counterparty_id": "all", "delay_days": 20}}
  ]}
}
```

Steps apply in order to the same copy. The returned economics include each step's
own narrative, so a compound result can still be decomposed.

---

## Validation

Every handler validates its inputs and raises `ScenarioError` with a readable
message, surfaced as HTTP 422. `tests/test_three_state.py::test_scenario_handlers_all_run`
executes **every catalogue entry with its published defaults** and asserts each
produces a narrative and a correctly-shaped cash path — so a scenario cannot be
added to the UI catalogue without being executable.

## What a scenario is not

It is not a plan, a commitment, or a prediction that the modelled event will happen.
It answers *"if this, then what"* — and the result always ends with the sentence
that nothing was written to the ledger.
