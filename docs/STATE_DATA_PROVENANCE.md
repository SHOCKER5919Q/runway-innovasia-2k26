# State data provenance

*Detail page for `THREE_STATE_ARCHITECTURE.md`.*

Any figure on any screen can be traced to the source record that produced it. This
page shows how.

---

## The evidence hierarchy

| Rank | Class | Meaning | Example |
|---:|---|---|---|
| 1 | `verified_actual` | Reconciled against a source document | A receipt matched to an invoice by its bank reference |
| 2 | `imported_actual` | From a feed, not yet verified | A row from a CSV, unmatched |
| 3 | `owner_estimate` | Typed in by a human | An expected payroll amount |
| 4 | `model_prediction` | Produced by a forecaster | A predicted payment date |
| 5 | `scenario_assumption` | A what-if input | "Advance = 30%" |
| 6 | `simulation_output` | Computed from (5) | The resulting minimum cash |

**Demotion is free. Promotion is audited.** When an owner corrects a transaction's
category, it becomes `verified_actual` and the correction is appended to that row's
transformation log with the user id and the before/after values.

---

## What a transaction carries

```json
{
  "id": "16cac32e67d742e7b211b589e659a5ca",
  "value_date": "2026-11-05",
  "amount_paise": 13234600,
  "direction": "credit",
  "narration": "NEFT CR-ABC DISTRIBUTORS-INV-1807",
  "reference_no": "NEFT993188210",
  "category": "customer_receipt",
  "category_confidence": 0.92,
  "category_source": "Generic inbound payment",
  "evidence": "verified_actual",
  "recon_status": "matched",
  "source_system": "bank_csv",
  "import_batch_id": "...",

  "raw_json": { "Date": "05/11/2026", "Narration": "...", "Deposit Amt": " 132346.00 " },

  "transform_log_json": [
    {"step": "parse", "adapter": "bank_csv", "file": "hdfc-nov.csv"},
    {"step": "duplicate_check", "result": "unique"},
    {"step": "resolve_counterparty", "result": "matched 'ABC Distributors' on narration tokens (0.97)", "confidence": 0.97},
    {"step": "classify", "category": "customer_receipt", "confidence": 0.92, "rule": "Generic inbound payment"},
    {"step": "reconcile", "status": "matched", "note": "NEFT reference quotes INV-1807"}
  ]
}
```

`raw_json` is the source row **verbatim**. `transform_log_json` is every step
applied to it, in order. Neither is ever discarded.

The Transactions screen renders this chain, so a figure traces to its source in two
clicks.

---

## Tracing a predicted closing balance

```
closing[week 6]  P50 ₹20,26,000
  │
  ├── opening cash                    ₹9,07,195   verified_actual
  │     └── 3 accounts, each: opening + credits − debits
  │           └── 1,864 transactions, each with its raw source row
  │
  ├── + open receivables landing in w6
  │     └── 18 invoices, each with:
  │           - outstanding      verified_actual
  │           - predicted date   model_prediction (pdm-gbq-conformal-1.2.0)
  │           - driver contributions by ablation
  │
  ├── + sales not yet invoiced        estimated
  │     └── de-seasonalised median × seasonality × damped trend
  │           basis, trend ratio and CV all recorded in assumptions
  │
  ├── − open payables due in w6       verified_actual
  │     └── scheduled at min(contractual due, MSMED statutory deadline)
  │
  ├── − obligations                   mixed
  │     └── payroll and rent: contractual
  │     └── GST: RUNWAY estimate, basis recorded (output tax − input credit)
  │
  └── − recurring operating costs     estimated
        └── trailing mean over 180 days, by category
```

Every level is visible: the Cash Runway screen shows the driver breakdown with each
item's evidence class, and the assumptions block is returned verbatim in the API.

---

## Tracing a simulated figure

A simulated value adds one more layer, and that layer is recorded in full:

```
SimulatedSnapshot
  baseline_actual_state_id      the reality it branched from
  baseline_predicted_state_id   the forecast it branched from
  parameters_json               every scenario input
  outputs_json.economics        what the handler derived from them
  seed                          the exact random draws
```

So a simulated minimum cash of ₹2,10,926 traces to: a specific forecast, built from
a specific ledger state, with a specific fingerprint, mutated by a specific
parameter set, under a specific seed. Re-running reproduces it exactly.

---

## Where provenance is shown

| Screen | What it exposes |
|---|---|
| Transactions → detail | The full transformation chain and the raw source row |
| Invoices → detail | Every allocation with its matching rationale and confidence |
| Cash Runway → method | Every assumption, the correlation source, the model's selection note |
| Business State Centre | State versions, fingerprint, engine version, data quality |
| Risk Centre | Per-alert evidence lists |
| Recommendations | Triggering evidence and the five ranking terms |
| Copilot | Evidence list plus the state versions the answer was computed from |
| Reports → Passport | A verification class per section |
| Digital Twin → activity | Every rebuild, forecast and scenario, in order |

---

## What provenance cannot tell you

It records where a number came from, not whether the source was right. A
mis-recorded invoice amount propagates with full provenance intact.

The defences against that are the data-quality score, the "needs review" queue, and
the owner's ability to correct — all of which are themselves logged. But the honest
statement is that provenance makes errors **traceable**, not impossible.
