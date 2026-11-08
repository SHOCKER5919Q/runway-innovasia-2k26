# Digital twin architecture

## What the twin is

A continuously-rebuilt computational representation of how one business behaves
financially. Not a dashboard of the current state — a model that can be queried
about the past, the likely future, and futures that do not exist.

It is the layer that connects everything else: the ledger feeds it, the forecaster
extends it, the scenario engine branches it, the risk engine interrogates it, and
the copilot reads it.

## Components

```
app/digital_twin/
├── digital_twin_service.py   assembles and caches the complete bundle
├── relationship_graph.py     entities and the money flowing between them
├── temporal_state.py         one ordered stream of past and future events
├── scenario_engine.py        12 decision types, each a pure mutation
└── decision_optimizer.py     risk-adjusted ranking of alternatives

app/financial_states/
└── state_manager.py          actual | predicted | simulated, versioned
```

## The bundle

One computation per `(business, as_of, ledger_fingerprint)`, cached for 180 seconds:

```python
TwinBundle:
    actual_state, predicted_state        versioned headers
    actual_snapshot, predicted_snapshot  the data
    position, simulation, forecast_inputs
    predictions          invoice → predicted payment date and probabilities
    behaviour            per-customer payment statistics
    collection_list      prioritised receivables
    ageing_ar/ap, supplier_profiles, payment_calendar, msmed
    concentration, correlation, obligations, coverage
    health, anomalies, stress, sensitivity
    findings             early-warning alerts
    recommendations      ranked actions
    working_capital, flow_30d, data_quality
```

Every screen and every copilot tool reads this same object. That is why two parts of
the product can never disagree about a number: there is only one computation, and it
is keyed on a hash of the ledger's contents rather than on a timer.

## Lifecycle

```
ledger change (import, correction, manual entry)
   │
   ├─ invalidate(business_id)
   │
   └─ next read:
        fingerprint differs
          → build_actual()      version n+1, previous superseded not deleted
          → build_predicted()   train → predict → simulate → version m+1
          → analytics, risk, recommendations recomputed
          → alerts reconciled: resolved ones closed, new ones opened
          → twin_events row written
```

Rebuilds are inline. Cold they take ~5 seconds, dominated by fitting four
gradient-boosting models; warm ~0.8 s; cached ~3 ms. At MSME scale a queue would add
a broker, a worker and a class of partial-failure states to save four seconds on a
rare path. `PROJECT_STATUS.md` records when that trade-off flips.

## The business state model

### Financial state
Bank and cash balances, restricted, committed, available liquidity, overdraft
headroom, receivables and their overdue split, payables, loan outstanding, working
capital, 30-day revenue and expense. Cash, accounting revenue, profit and
receivables are kept distinct — **an unpaid invoice is never available cash**.

### Customer state
Per buyer: historical volume, revenue share, open and overdue exposure, oldest
overdue, contractual terms, mean / median / P90 payment delay, delay standard
deviation, on-time rate, partial-payment rate, DSO, a reliability score, a risk
band, the evidence behind all of it, and a data-confidence figure that falls when
there are too few settled invoices to be sure.

### Supplier state
Per supplier: spend share, concentration flag, open and overdue balances, mean days
to pay, contractual terms, early-payment discount and its annualised equivalent,
MSMED class, and MSMED-exposed amount with breach count.

### Operational state
**Deliberately empty.** Inventory levels, purchase orders, sales orders, production
commitments and branch activity are listed as *missing* with a note explaining that
no source is connected. The cash-conversion metric says the same thing on screen.
Inventing a stock figure to complete a diagram would be the single most damaging
thing this product could do.

### Obligation state
GST, TDS, payroll, PF/ESI, rent, loan EMIs, insurance and supplier commitments —
each with source, amount, expected date, evidence class and payment status.
Estimated items are labelled as estimates everywhere they appear.

## Relationship graph

Nodes: the business, its accounts, customers, suppliers, open invoices, obligations
and loans. Edges carry direction and amount: `customer —owes→ business`,
`business —owes→ supplier`, `invoice —belongs to→ counterparty`,
`business —must pay→ obligation`.

Built from three relational queries in ~56 ms for 66 nodes and 65 edges. A graph
database would add a second datastore and buy nothing at this size; the threshold at
which it would pay is multi-hop traversal — "which of my customers share a supplier
with my largest customer" — which is a real question and is not asked today.

The layout is a deterministic radial arrangement computed in the browser: customers
left, suppliers right, accounts above, obligations below, node radius proportional
to √(exposure). Deterministic matters — a force-directed graph that settles
differently on every load is unreadable as a reference.

## Temporal twin

One ordered event stream across past and future:

| Certainty | Meaning | Example |
|---|---|---|
| `actual` | Recorded and reconciled | A receipt that cleared last Tuesday |
| `contractual` | A known commitment with a fixed date | An EMI, a supplier invoice |
| `estimated` | Derived by RUNWAY, not from a filed document | A GST liability |
| `predicted` | A model estimate with a range | A customer payment, with P10 and P90 dates |

The weekly roll-up reports a **predicted share** per week — how much of that week's
movement rests on a model rather than a dated commitment. A week that is 90%
predicted is far less certain than its total suggests, and the interface says so.

## Validation

- **Immutable versioning** with full lineage pointers.
- **Ledger fingerprint** on every state, proving which data produced it.
- **Data-quality score** with specific warnings, surfaced wherever it matters.
- **Staleness detection** in days since the last transaction.
- **Backtesting**: stored forecasts resolved against recorded outcomes.
- **Activity log**: every rebuild, forecast and scenario run, with a summary.

## Honest boundaries

The twin models **cash and commitments**. It does not model inventory, production
capacity, people, demand, or anything a human knows and has not written down. It
states what it does not know rather than filling the gap, because a twin that
quietly invents the missing half is worse than no twin at all.
