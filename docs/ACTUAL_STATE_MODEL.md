# Actual state model

*Companion to `THREE_STATE_ARCHITECTURE.md`, which covers all three states together.*

## Definition

The actual state is what is **recorded**, reconstructed from the reconciled ledger
at a given date. It contains no prediction and no assumption.

## Construction

`app/financial_states/state_manager.py::build_actual`

```
1. ledger_fingerprint(business, as_of)   hash of the material ledger contents
2. if a current state exists with this fingerprint → reuse it
3. cash_position()        per-account opening + credits − debits, as of the date
4. working_capital()      current assets vs current liabilities
5. flow_summary(30d)      inflow / outflow / net by category
6. receivables, payables  as-of outstanding, overdue split
7. data_quality()         verified / reconciled / categorised / fresh
8. supersede the previous current state; write version n+1
```

Step 2 is what makes this cheap: an unchanged ledger produces no new version, so
reading the dashboard a hundred times creates one state, not a hundred.

## Point-in-time reconstruction

`app/ledger/asof.py` is the only place this happens:

```python
def outstanding_at(inv, as_of):
    if inv.issue_date > as_of:                 return 0   # not issued yet
    if inv.status in (CANCELLED, WRITTEN_OFF): return 0
    if inv.settled_date and inv.settled_date <= as_of:  return 0
    if inv.first_payment_date and inv.first_payment_date <= as_of:
        return total − settled                            # part paid by then
    return total
```

This exists because of a bug worth recording. The first implementation of the
historical backfill used each invoice's *current* `outstanding_paise`. Evaluating
15 August therefore saw only the invoices still unpaid in November — about 3 of
them instead of 104. The forecasts it produced were wildly pessimistic, and the
backtest was measuring a model that had never existed. After the fix, long-horizon
bias moved from −₹17 lakh to approximately zero and short-horizon band coverage rose
from 0% to 100%.

Any system that backtests must reconstruct the world as it was. Most do not.

## Cash decomposition

| Component | Source | Note |
|---|---|---|
| Cash in hand | Σ account closing balances | The bank statement figure |
| Restricted | `account.restricted_paise`, capped at the balance | Lien-marked FDs, pledged deposits |
| Committed | Obligations with `reserve_cash` due within 30 days | GST and payroll the owner has ring-fenced |
| **Available liquidity** | cash − restricted − committed | **The number that matters** |
| Overdraft headroom | Σ limits − Σ negative balances | Reported separately; it is credit |

## Evidence and provenance

Every transaction retains:

- `raw_json` — the source row, verbatim
- `transform_log_json` — every step applied, in order: parse → duplicate check →
  counterparty resolution → classification → reconciliation → any owner correction
- `source_system`, `source_ref`, `import_batch_id`
- `evidence` — its class in the hierarchy
- `category_confidence` and the rule that produced it

The Transactions screen renders the whole chain, so any figure on any screen can be
traced to its source record in two clicks.

## Invariants

See `THREE_STATE_ARCHITECTURE.md` § State 01. All five are enforced in
`tests/test_ledger_invariants.py` and auditable outside pytest with
`scripts/verify_ledger.py`.
