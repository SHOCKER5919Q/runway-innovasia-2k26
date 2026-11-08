# State versioning

*Detail page for `THREE_STATE_ARCHITECTURE.md`.*

## The rule

**A state is immutable once written. A new state supersedes; it never replaces.**

```sql
business_states
  id                   32-char hex
  business_id
  state_type           actual | predicted | simulated
  version              monotonic per (business, state_type)
  as_of_date           the date the state describes
  created_at           when it was computed
  source_state_id      lineage: predicted → actual, simulated → predicted
  engine_version
  ledger_fingerprint
  data_quality_json
  status               current | superseded
  trigger              what caused it
  UNIQUE (business_id, state_type, version)
```

Superseding sets `status = 'superseded'`. Nothing is deleted, ever.

## Why

Scoring a forecast requires the forecast **as it was made**. A system that
overwrites its predictions can never honestly report accuracy — which is precisely
why so many products quote an accuracy figure from a slide deck rather than from
their own database.

Three concrete consequences:

1. A saved scenario stays comparable against the baseline it was actually run on.
2. A recorded decision can be evaluated months later against what the owner saw
   when they made it.
3. `forecast_points` rows can be resolved against reality as weeks elapse.

## The ledger fingerprint

```python
sha256(f"{as_of}|{txn_count}|{txn_amount_sum}|{txn_max_updated_at}"
       f"|{inv_count}|{inv_settled_sum}|{inv_total_sum}")[:40]
```

Two states with the same fingerprint describe the same financial reality.

This does two jobs. It is the **cache key**, so re-reading the dashboard a hundred
times creates one state rather than a hundred. And it is the **proof of provenance**
— a predicted state carries the fingerprint of the actual state it was built from,
so the question "which data produced this forecast?" has an exact answer.

## When versions are created

| Trigger | Produces |
|---|---|
| Import committed | Fingerprint changes → actual v(n+1) → predicted v(m+1) |
| Owner corrects a transaction | Same |
| Manual refresh | Both, with `reuse=False`, even if the fingerprint is unchanged |
| Dashboard read, ledger unchanged | **Nothing.** The existing current state is reused |
| Scenario run | A simulated state. Actual and predicted are untouched |

## Lineage

```
ActualState v5  (fingerprint abc123…)
   └── PredictedState v5     source_state_id = actual v5
          ├── SimulatedState v12   baseline_actual = v5, baseline_predicted = v5
          ├── SimulatedState v13   baseline_actual = v5, baseline_predicted = v5
          └── SimulatedState v14   baseline_actual = v5, baseline_predicted = v5
```

All three simulated states share a baseline, so they are directly comparable. The
comparison endpoint reports `all_share_baseline` and warns when they do not:

> These scenarios were run against different baselines, so the comparison is
> indicative rather than exact. Re-run them to align.

## Baseline pinning

A `Scenario` row stores `baseline_actual_state_id` and
`baseline_predicted_state_id` at creation. Re-running uses **those**, not whatever
is current.

A system that silently re-baselined would make every recorded decision unauditable
a month later — the owner would see different numbers than the ones they decided on,
with no indication that anything had changed.

Asserted by `tests/test_workflow_e2e.py::test_10_a_saved_scenario_pins_its_baseline`.

## Growth

Each actual state is one header plus one snapshot row. Each predicted state adds 13
`forecast_points` and one `payment_predictions` row per open invoice — roughly 125
rows for the demo business. At a realistic rebuild cadence of a few per day that is
~50k rows a year per business, which is nothing.

Retention is not implemented and is not currently needed. When it is, the right
policy is to thin old *predicted* states to their forecast points (which are what
accuracy measurement needs) while keeping every actual state.

## Reading history

```
GET /api/states/history?state_type=predicted&limit=40
```

Returns every version with its type, as-of date, creation time, lineage, status,
trigger, engine version, fingerprint and data-quality score. Rendered in the
Business State Centre and in the twin's activity log.
