# Three-state testing

*Detail page for `THREE_STATE_ARCHITECTURE.md`. General testing is in `TESTING.md`.*

The three-state model is only worth having if it is enforced. These are the tests
that enforce it.

```bash
./run.sh test                                      # all 191
backend/.venv/bin/python -m pytest tests/test_three_state.py -v
```

---

## Actual state

| Test | Asserts | File |
|---|---|---|
| `test_opening_plus_credits_minus_debits_equals_closing` | The balance identity holds exactly, per account | `test_ledger_invariants.py` |
| `test_no_allocation_exceeds_its_invoice` | Reconciliation cannot create money | `test_ledger_invariants.py` |
| `test_no_allocation_exceeds_its_transaction` | Allocation never exceeds the settleable amount (**caught the gateway-fee double-allocation bug**) | `test_ledger_invariants.py` |
| `test_settled_equals_sum_of_allocations` | The derived field matches its parts | `test_ledger_invariants.py` |
| `test_an_unpaid_invoice_is_never_counted_as_cash` | Cash = opening + net transactions, with receivables excluded | `test_ledger_invariants.py` |
| `test_cash_position_decomposition` | available = cash − restricted − committed, and overdraft is kept separate | `test_ledger_invariants.py` |
| `test_identical_reference_is_a_hard_duplicate` | A shared bank reference rejects the row | `test_reconciliation.py` |
| `test_same_amount_without_reference_is_only_suspected` | **Flagged, never deleted** | `test_reconciliation.py` |
| `test_partial_payment_leaves_the_invoice_open` | Partial settlement works | `test_reconciliation.py` |
| `test_reconciliation_is_idempotent` | A second pass allocates nothing extra | `test_reconciliation.py` |
| `test_an_owner_correction_is_recorded_as_verified` | Promotion is audited in the transform log | `test_api_and_security.py` |

---

## Predicted state

| Test | Asserts |
|---|---|
| `test_predicted_state_names_the_actual_state_it_came_from` | Lineage and fingerprint are carried |
| `test_old_forecasts_remain_queryable` | Superseding preserves; versions are unique |
| `test_quantile_paths_are_ordered` | P10 ≤ P25 ≤ P50 ≤ P75 ≤ P90, every week |
| `test_bucket_zero_is_todays_balance` | Bucket 0 carries no flows |
| `test_same_seed_gives_identical_results` | Full reproducibility |
| `test_conformal_calibration_improves_coverage` | Calibration measurably helps |
| `test_quantiles_never_cross` | Including after an overdue invoice is re-anchored |
| `test_probabilities_are_monotone_in_the_horizon` | P(7) ≤ P(15) ≤ P(30) |
| `test_a_predicted_payment_date_is_never_in_the_past` | Re-anchoring works |
| `test_model_is_never_shipped_unless_it_beats_its_baseline` | **The selection guard holds** |
| `test_the_horizon_truncation_limit_is_disclosed` | The limitation is in the output, not only the docs |
| `test_15_forecast_accuracy_is_measured_not_claimed` | When nothing has matured, nothing is claimed |

### The monotonicity tests

```python
def test_paying_earlier_can_only_help():      # min cash ↑, breach ↓
def test_paying_later_can_only_hurt():        # min cash ↓
```

Properties that must hold for any correct implementation. **Both caught real bugs** —
the calendar-Monday week anchoring and the horizon clipping. Neither would have been
visible by looking at a chart.

---

## Simulated state

| Test | Asserts |
|---|---|
| `test_a_scenario_never_writes_to_the_ledger` | A ₹50 lakh simulated loan changes nothing: transaction count, invoice count, allocation count and total settled are all identical before and after |
| `test_applying_a_scenario_does_not_mutate_the_baseline_inputs` | Two scenarios run against one inputs object leave it byte-identical |
| `test_branches_share_the_baseline_and_the_seed` | Under common random numbers, a 30% advance **provably** improves minimum cash and cannot raise breach probability |
| `test_scenario_handlers_all_run` | Every catalogue entry executes with its published defaults and returns a correctly-shaped path |
| `test_an_unknown_scenario_kind_is_rejected` | Unknown kinds raise, not silently no-op |
| `test_msmed_protected_invoices_are_not_deferred_by_default` | Micro/small supplier invoices are untouched by a supplier-terms scenario |
| `test_10_a_saved_scenario_pins_its_baseline` | Re-running uses the original baseline, not the current one |
| `test_12_a_decision_can_be_recorded_without_touching_the_ledger` | Cash is unchanged after marking a scenario implemented |

---

## Cross-state

| Test | Asserts |
|---|---|
| `test_actual_state_is_reused_while_the_ledger_is_unchanged` | Fingerprint-keyed reuse works |
| `test_a_ledger_change_produces_a_new_version` | A new transaction changes the fingerprint, bumps the version, and **leaves the old state queryable with `status='superseded'`** |
| `test_an_answer_always_declares_its_state` | Every copilot answer names its state |
| `test_a_scenario_answer_states_the_isolation_guarantee` | Simulated answers say nothing was written |
| `test_every_answer_is_traceable_to_a_state_version` | State refs and fingerprint accompany every answer |
| `test_the_briefing_labels_every_line_with_its_state` | No unlabelled line reaches the dashboard |
| `test_a_user_cannot_read_a_business_they_do_not_belong_to` | **403**, not an empty result |
| `test_tool_schema_exposes_no_business_parameter` | No tool can be pointed at another tenant |

---

## Running just the three-state surface

```bash
cd runway-innovasia-2k26   # the repository root
backend/.venv/bin/python -m pytest \
  tests/test_three_state.py \
  tests/test_ledger_invariants.py \
  tests/test_forecast.py -v
```

36 tests, ~50 seconds.

---

## What these tests cannot prove

They prove the **mechanism** is correct: states are separated, versions are
immutable, scenarios are isolated, and the arithmetic does not lose money.

They cannot prove the **model** is right. That is a separate, empirical question,
answered by `reconcile_forecasts()` and reported in `EVALUATION_RESULTS.md` — where
the honest answer today is "good at short horizons, poor and thinly measured at
long ones".
