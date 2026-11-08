# Product vision

## The problem

An Indian MSME owner already has software. Tally records their accounts, Vyapar
manages their transactions, their bank provides statements, the GST portal takes
their returns, a gateway settles their payments. None of it is wrong. All of it is
disconnected.

So the owner carries the integration in their head. They know roughly who owes them,
roughly when payroll is due, roughly whether they can take the order in front of
them. The knowledge is real but it is unaided, and it fails in exactly the situation
where it matters most: when several things go slightly wrong at once.

The failure mode is not insolvency on paper. It is a profitable business that cannot
pay its people in week eight because an order it accepted in week one required
₹12 lakh of materials forty days before the customer's sixty-day terms expired.

## The position

RUNWAY is not another accounting application. It does not want to replace Tally, and
it does not want the owner to migrate anything.

It is the **intelligence layer** that sits on top of what they already have:

```
Tally · Vyapar · banks · GST portal · gateways   ← what they keep
                     │
              ┌──────▼──────┐
              │   RUNWAY    │                     ← what connects them
              └──────┬──────┘
         understanding · foresight · decisions
```

The thesis in one line: **make the software they already use more valuable, rather
than asking them to abandon it.**

## What it does that nothing else does

**It separates reality from expectation.** Every number says whether it is recorded,
predicted or simulated. That sounds like a presentation detail. It is the whole
product — because a forecast rendered like a bank balance is how an owner ends up
spending money that has not arrived.

**It answers the question actually being asked.** "Can I afford this order?" is not
a margin question. RUNWAY answers with the funding gap: how many days, and how much,
between paying for the materials and being paid for the goods.

**It measures itself.** Stored forecasts are scored against what actually happened,
per horizon, and the bad horizons are shown with their sample size. A product that
only reports its wins is not reporting.

**It refuses.** When it cannot source a figure, it says so. When its own model loses
to a baseline, it ships the baseline and says that too. In a product about someone
else's money, the refusals are more valuable than the features.

## Who it is for

**Primarily** — the owner of a ₹1–50 crore turnover MSME who makes the cash
decisions personally and currently makes them on instinct and a bank balance.

**Also** — the chartered accountant serving twenty such businesses, who needs
exception-based oversight rather than twenty dashboards. The accountant workspace
exists because CAs are the distribution channel for this category: they are trusted,
they already hold the data, and they are asked "can I afford this?" constantly.

**Eventually** — the lender who needs a view of a business's cash behaviour that is
richer than a bank statement and more current than a balance sheet, supplied by the
business itself under its own consent.

## The twelve capabilities

| | | State |
|---|---|---|
| 1 | Cash runway intelligence | Actual + Predicted |
| 2 | Predictive receivables intelligence | Actual + Predicted |
| 3 | Supplier and procurement intelligence | Actual |
| 4 | Financial survival simulator | Simulated |
| 5 | Business financial health score | Actual + Predicted |
| 6 | Early warning and survival system | Predicted |
| 7 | Working-capital optimisation | Simulated |
| 8 | GST and statutory obligation intelligence | Actual |
| 9 | Financial intelligence copilot | All three |
| 10 | Cash Health Passport | Actual + Predicted |
| 11 | Industry-aware intelligence | All three |
| 12 | Accountant multi-business workspace | Actual + Predicted |

All twelve are implemented. `PROJECT_STATUS.md` records how completely.

## What it will never do

These are commitments, enforced in code and asserted in tests:

- **Never move money.** No payment, no credit application, no contract change.
  Every recommendation requires explicit approval.
- **Never claim to be a credit score.** The health indicator is RUNWAY's own,
  transparent, configurable, and carries its disclaimer into the API and the
  shared report.
- **Never promise loan approval.** Financing scenarios model cost and repayment.
  Availability is never implied.
- **Never publish an unmeasured accuracy figure.** Where nothing has matured, the
  product says nothing has matured.
- **Never let a model invent a number.** The copilot's figures are verified against
  deterministic tool output before display.
- **Never sell financial data.** Any future benchmarking must be consented and
  privacy-preserving.
- **Never present a simulation as a record.** Scenario isolation is structural, not
  procedural.

## Why distribution works through accountants

A CA serving twenty MSMEs has the data, the trust and the recurring conversation.
They are asked "can I afford this?" every week and currently answer from
experience. The accountant workspace makes them faster at that, which makes RUNWAY
spread through the people the owner already believes.

The alternative — direct acquisition of individual MSMEs — fights for attention
against a business owner's actual job. The CA is already in the room.

## Defensibility, honestly

RUNWAY's moat is not lock-in. The owner can export everything, and should be able to.

It is:

1. **Reconciled history.** Eighteen months of correctly matched payments is
   expensive to recreate and is what every prediction depends on.
2. **Counterparty behaviour.** Knowing that ABC Distributors has drifted from 8 to
   22 days late over a year is knowledge that only accumulates.
3. **Measured calibration.** A forecast whose intervals are demonstrably calibrated
   is worth more than one that is merely confident, and calibration takes time to
   earn.
4. **Workflow integration.** Being the thing the owner opens every morning.

The goal is not to make leaving difficult. It is to make the value of staying
obvious.

## What success looks like

Not a dashboard an owner admires. An owner who, in week two, says *"I was going to
take that order without an advance."*

One avoided liquidity crisis per business per year is the entire business case.
Everything else is in service of that sentence.
