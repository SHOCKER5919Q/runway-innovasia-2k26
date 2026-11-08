"""The three-state architecture's invariants."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.enums import DecisionStatus, ScenarioKind, StateType
from app.digital_twin.scenario_engine import ScenarioError, apply_scenario
from app.financial_states.state_manager import (
    build_actual, build_predicted, current, ledger_fingerprint, run_scenario,
)
from app.models import (
    Allocation, BusinessState, Invoice, PredictedSnapshot, Scenario,
    SimulatedSnapshot, Transaction, _uid,
)

TODAY = date(2026, 11, 7)


def test_actual_state_is_reused_while_the_ledger_is_unchanged(db, business_id):
    a1 = build_actual(db, business_id, TODAY, trigger="test")
    db.commit()
    a2 = build_actual(db, business_id, TODAY, trigger="test")
    assert a2.id == a1.id, "an unchanged ledger must not produce a new state version"


def test_a_ledger_change_produces_a_new_version(db, business_id):
    before = ledger_fingerprint(db, business_id, TODAY)
    a1 = build_actual(db, business_id, TODAY, trigger="test")
    db.commit()
    from app.core.enums import Direction, Evidence, ReconStatus
    from app.models import Account
    acct = db.scalars(select(Account).where(Account.business_id == business_id)).first()
    db.add(Transaction(id=_uid(), business_id=business_id, account_id=acct.id,
                       value_date=TODAY, amount_paise=12_345_00, direction=Direction.CREDIT,
                       narration="TEST LEDGER MUTATION", allocated_paise=0,
                       evidence=Evidence.IMPORTED_ACTUAL,
                       recon_status=ReconStatus.UNRECONCILED, fingerprint=_uid()))
    db.commit()
    after = ledger_fingerprint(db, business_id, TODAY)
    assert after != before
    a2 = build_actual(db, business_id, TODAY, trigger="test")
    db.commit()
    assert a2.id != a1.id
    assert a2.version == a1.version + 1
    # Superseding must preserve, never delete.
    assert db.get(BusinessState, a1.id) is not None
    assert db.get(BusinessState, a1.id).status == "superseded"


def test_predicted_state_names_the_actual_state_it_came_from(db, business_id):
    a = build_actual(db, business_id, TODAY, trigger="test")
    p, snap = build_predicted(db, business_id, a, paths=400, trigger="test")
    db.commit()
    assert p.source_state_id == a.id
    assert snap.baseline_actual_state_id == a.id
    assert p.ledger_fingerprint == a.ledger_fingerprint


def test_old_forecasts_remain_queryable(db, business_id):
    versions = db.scalars(select(BusinessState.version).where(
        BusinessState.business_id == business_id,
        BusinessState.state_type == StateType.PREDICTED)).all()
    assert len(versions) >= 2, "backfilled forecast history should be present"
    assert len(set(versions)) == len(versions), "versions must be unique"


# ── scenario isolation ────────────────────────────────────────────

def test_a_scenario_never_writes_to_the_ledger(db, business_id):
    def counts():
        return (
            db.scalar(select(func.count()).select_from(Transaction)
                      .where(Transaction.business_id == business_id)),
            db.scalar(select(func.count()).select_from(Invoice)
                      .where(Invoice.business_id == business_id)),
            db.scalar(select(func.count()).select_from(Allocation)
                      .where(Allocation.business_id == business_id)),
            db.scalar(select(func.coalesce(func.sum(Invoice.settled_paise), 0))
                      .where(Invoice.business_id == business_id)),
        )

    before = counts()
    a = current(db, business_id, StateType.ACTUAL) or build_actual(db, business_id, TODAY)
    p = current(db, business_id, StateType.PREDICTED)
    if p is None:
        p, _ = build_predicted(db, business_id, a, paths=400)
    db.commit()

    s = Scenario(id=_uid(), business_id=business_id, name="isolation probe",
                 kind=ScenarioKind.FINANCING,
                 parameters_json={"amount_paise": 50_00_000_00, "annual_rate": 0.18,
                                  "tenure_months": 12},
                 baseline_actual_state_id=a.id, baseline_predicted_state_id=p.id)
    db.add(s)
    db.commit()
    run_scenario(db, s, actual=a, predicted=p, paths=400)
    db.commit()

    assert counts() == before, "a simulated loan must not appear anywhere in the ledger"


def test_applying_a_scenario_does_not_mutate_the_baseline_inputs(db, business_id):
    from app.forecast.cashflow import build_inputs
    fi = build_inputs(db, business_id, TODAY, safety_buffer_paise=0)
    snapshot = ([i.day_offset for i in fi.inflows], [o.amount_paise for o in fi.outflows],
                list(fi.weekly_new_sales_paise), fi.cogs_ratio)
    apply_scenario(fi, ScenarioKind.PAYMENT_DELAY,
                   {"counterparty_id": "all", "delay_days": 45}, TODAY)
    apply_scenario(fi, ScenarioKind.REVENUE_SHOCK, {"drop_pct": 0.5}, TODAY)
    after = ([i.day_offset for i in fi.inflows], [o.amount_paise for o in fi.outflows],
             list(fi.weekly_new_sales_paise), fi.cogs_ratio)
    assert snapshot == after, "apply_scenario must work on a copy"


def test_branches_share_the_baseline_and_the_seed(db, business_id):
    from app.forecast.cashflow import build_inputs
    from app.forecast.monte_carlo import simulate
    fi = build_inputs(db, business_id, TODAY, safety_buffer_paise=3_00_000_00)
    a, _ = apply_scenario(fi, ScenarioKind.NEW_ORDER,
                          {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                           "advance_pct": 0.0, "credit_days": 60}, TODAY)
    b, _ = apply_scenario(fi, ScenarioKind.NEW_ORDER,
                          {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                           "advance_pct": 0.30, "credit_days": 60}, TODAY)
    ra, rb = simulate(a, paths=1200, seed=11), simulate(b, paths=1200, seed=11)
    # An advance is money sooner, so the worst week can only improve.
    assert rb.min_cash_p50_paise > ra.min_cash_p50_paise
    assert rb.breach_probability <= ra.breach_probability


def test_an_unknown_scenario_kind_is_rejected(db, business_id):
    from app.forecast.cashflow import build_inputs
    fi = build_inputs(db, business_id, TODAY, safety_buffer_paise=0)
    with pytest.raises(ScenarioError):
        apply_scenario(fi, "teleport_the_money", {}, TODAY)


def test_scenario_handlers_all_run(db, business_id):
    """Every catalogue entry must execute with its published defaults."""
    from app.digital_twin.scenario_engine import CATALOGUE
    from app.forecast.cashflow import build_inputs
    from app.forecast.monte_carlo import simulate
    fi = build_inputs(db, business_id, TODAY, safety_buffer_paise=3_00_000_00)
    for entry in CATALOGUE:
        params = {p["key"]: p["default"] for p in entry["params"]}
        f, extras = apply_scenario(fi, entry["kind"], params, TODAY)
        r = simulate(f, paths=300, seed=5)
        assert "narrative" in extras, entry["kind"]
        assert len(r.p50) == f.horizon_weeks + 1, entry["kind"]


def test_msmed_protected_invoices_are_not_deferred_by_default(db, business_id):
    from app.forecast.cashflow import build_inputs
    fi = build_inputs(db, business_id, TODAY, safety_buffer_paise=0)
    protected_before = [(o.label, o.day_offset) for o in fi.outflows
                        if o.kind == "supplier_invoice" and not o.flexible]
    f, extras = apply_scenario(fi, ScenarioKind.SUPPLIER_TERMS,
                               {"extra_days": 30, "respect_msmed": True}, TODAY)
    protected_after = [(o.label, o.day_offset) for o in f.outflows
                       if o.kind == "supplier_invoice" and not o.flexible]
    assert protected_before == protected_after, (
        "deferring a micro/small supplier risks a 43B(h) disallowance and must not "
        "happen unless the owner explicitly overrides it")
    assert extras["respected_msmed"] is True
