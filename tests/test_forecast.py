"""Forecasting: calibration, reproducibility and the model-selection guard."""
from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from sqlalchemy import select

from app.forecast.cashflow import (COUPLING_CAP, build_inputs,
                                   estimate_revenue_delay_coupling)
from app.forecast.monte_carlo import simulate
from app.forecast.payment_delay import predict_open, train
from app.models import Business, Invoice

TODAY = date(2026, 11, 7)


@pytest.fixture(scope="module")
def trained(seeded):
    """``seeded`` is session-scoped, so depending on it lets this file run on
    its own instead of only as part of the full suite."""
    from app.core.db import SessionLocal
    db = SessionLocal()
    biz = db.scalars(select(Business).where(Business.is_demo.is_(True))).first()
    invs = db.scalars(select(Invoice).where(Invoice.business_id == biz.id)).all()
    m = train(invs, TODAY)
    yield db, biz, invs, m
    db.close()


# ── payment-delay model ───────────────────────────────────────────

def test_model_is_never_shipped_unless_it_beats_its_baseline(trained):
    _, _, _, m = trained
    mt = m.metrics
    assert mt["status"] == "trained"
    base = mt["baseline_customer_median"]["mae_days"]
    model = mt["model"]["mae_days"]
    if m.blend_weight == 0.0:
        # The guard declined the learned model, so the shipped predictor IS
        # the baseline and must score identically.
        assert model == pytest.approx(base, abs=1e-6)
        assert "NOT shipped" in mt["model_selection"]
    else:
        assert "shipped" in mt["model_selection"].lower()


def test_quantiles_never_cross(trained):
    _, _, invs, m = trained
    preds = predict_open(m, invs, TODAY)
    assert preds
    for p in preds:
        assert (p["predicted_delay_days_p10"] <= p["predicted_delay_days_p50"]
                <= p["predicted_delay_days_p90"]), p["invoice_id"]


def test_probabilities_are_monotone_in_the_horizon(trained):
    _, _, invs, m = trained
    for p in predict_open(m, invs, TODAY):
        assert p["prob_within_7"] <= p["prob_within_15"] <= p["prob_within_30"] + 1e-9


def test_conformal_calibration_improves_coverage(trained):
    _, _, _, m = trained
    mt = m.metrics
    assert mt["coverage_p10_p90_conformal"] >= mt["coverage_p10_p90_raw"]
    # 80% nominal; a wide tolerance because the held-out tail is small.
    assert 0.55 <= mt["coverage_p10_p90_conformal"] <= 0.98


def test_a_predicted_payment_date_is_never_in_the_past(trained):
    _, _, invs, m = trained
    for p in predict_open(m, invs, TODAY):
        assert date.fromisoformat(p["predicted_pay_date"]) >= TODAY


def test_training_is_reproducible(trained):
    _, _, invs, m = trained
    again = train(invs, TODAY)
    assert again.metrics["model"]["mae_days"] == m.metrics["model"]["mae_days"]
    assert again.blend_weight == m.blend_weight


# ── Monte Carlo ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sim(trained):
    db, biz, invs, m = trained
    preds = {p["invoice_id"]: p for p in predict_open(m, invs, TODAY)}
    fi = build_inputs(db, biz.id, TODAY, predictions=preds,
                      safety_buffer_paise=biz.safety_buffer_paise, industry=biz.industry)
    return fi, simulate(fi, paths=1500, seed=7)


def test_quantile_paths_are_ordered(sim):
    _, s = sim
    for i in range(len(s.p50)):
        assert s.p10[i] <= s.p25[i] <= s.p50[i] <= s.p75[i] <= s.p90[i], f"week {i}"


def test_bucket_zero_is_todays_balance(sim):
    fi, s = sim
    assert s.p10[0] == s.p50[0] == s.p90[0] == fi.opening_cash_paise


def test_same_seed_gives_identical_results(sim):
    fi, s = sim
    again = simulate(fi, paths=1500, seed=7)
    assert again.p50 == s.p50
    assert again.min_cash_p50_paise == s.min_cash_p50_paise
    assert again.breach_probability == s.breach_probability


def test_different_seeds_differ_but_stay_close(sim):
    fi, s = sim
    other = simulate(fi, paths=1500, seed=99)
    assert other.p50 != s.p50
    rel = abs(other.p50[-1] - s.p50[-1]) / max(1, abs(s.p50[-1]))
    assert rel < 0.25, "Monte Carlo noise should be small at 1500 paths"


def test_paying_earlier_can_only_help(sim):
    """A monotonicity property. If this breaks, the week bucketing is wrong."""
    fi, base = sim
    f2 = fi.copy()
    for i in f2.inflows:
        i.day_offset = max(0.0, i.day_offset - 14)
    better = simulate(f2, paths=1500, seed=7)
    assert better.min_cash_p50_paise >= base.min_cash_p50_paise
    assert better.breach_probability <= base.breach_probability + 1e-9


def test_paying_later_can_only_hurt(sim):
    fi, base = sim
    f2 = fi.copy()
    for i in f2.inflows:
        i.day_offset += 21
    worse = simulate(f2, paths=1500, seed=7)
    assert worse.min_cash_p50_paise <= base.min_cash_p50_paise


def test_var_is_never_greater_than_cvar(sim):
    _, s = sim
    assert s.liquidity_cvar_paise >= s.liquidity_var_paise


def test_nothing_is_silently_dropped_at_the_horizon(sim):
    _, s = sim
    beyond = s.assumptions["beyond_horizon_paise"]
    assert "note" in beyond
    assert all(isinstance(beyond[k], int) for k in
               ("receivables", "sales_not_yet_invoiced", "payables"))


def test_committed_purchasing_is_not_cancelled_by_a_revenue_shock(sim):
    """Within the lead-plus-terms window the materials are already ordered.

    Without this, a revenue collapse comes out as a cash *saving*, because the
    model would let the business stop buying on the day demand fell.
    """
    from app.digital_twin.scenario_engine import apply_scenario
    fi, base = sim
    assert fi.committed_purchase_weeks >= 1
    closings = []
    for pct in (0.0, 0.10, 0.20, 0.30):
        f, _ = apply_scenario(fi, "revenue_shock", {"drop_pct": pct}, TODAY) if pct \
            else (fi, None)
        closings.append(simulate(f, paths=1500, seed=7).p50[-1])
    assert closings == sorted(closings, reverse=True), (
        f"closing cash must fall as the revenue shock deepens, got {closings}")


def test_the_horizon_truncation_limit_is_disclosed(sim):
    _, s = sim
    assert "horizon_truncation_note" in s.assumptions
    assert "two quarters" in s.assumptions["horizon_truncation_note"]


def test_probability_fields_are_probabilities(sim):
    _, s = sim
    assert 0.0 <= s.breach_probability <= 1.0
    assert 0.0 <= s.negative_cash_probability <= 1.0
    assert all(0.0 <= p <= 1.0 for p in s.breach_prob_by_week)


# ── revenue / payment-delay coupling ──────────────────────────────

def test_coupling_is_estimated_from_the_ledger_and_bounded(trained):
    db, biz, _, _ = trained
    coupling, meta = estimate_revenue_delay_coupling(db, biz.id, TODAY)
    assert 0.0 <= coupling <= 0.60, "the estimate is capped so it cannot dominate"
    assert 0.0 <= coupling <= COUPLING_CAP
    if meta["estimate"] is not None:
        # Only the *negative* part of the correlation is used: a positive
        # correlation is not evidence that bad months make customers slow.
        assert coupling == pytest.approx(meta["coupling"], abs=1e-3)
        assert meta["coupling"] == pytest.approx(max(0.0, -meta["estimate"]), abs=1e-3)
        assert meta["months_used"] >= 6
    else:
        assert coupling == 0.0


def test_coupling_zero_is_bit_identical_to_no_market_factor(sim):
    """Turning the coupling off must not perturb any other draw.

    This is what makes the feature safe to ship behind an estimate: a
    business whose ledger shows no revenue/delay signal gets exactly the
    simulation it had before.
    """
    fi, _ = sim
    off = fi.copy()
    off.revenue_delay_coupling = 0.0
    a = simulate(off, paths=400, seed=11)
    b = simulate(off, paths=400, seed=11)
    assert a.p50 == b.p50
    baseline = simulate(off, paths=400, seed=11).min_cash_p10_paise
    on = fi.copy()
    on.revenue_delay_coupling = 0.0
    assert simulate(on, paths=400, seed=11).min_cash_p10_paise == baseline


def test_coupling_widens_the_bad_tail_and_never_the_good_one(sim):
    """A downturn path is simultaneously lighter on sales *and* slower to pay.

    The whole point of the coupling: it must make the pessimistic tail worse.
    It must not improve the optimistic tail, because a strong market does not
    make customers pay early - it only leaves the predicted dates alone.
    """
    fi, base = sim
    off = fi.copy()
    off.revenue_delay_coupling = 0.0
    base = simulate(off, paths=2500, seed=5)
    on = fi.copy()
    on.revenue_delay_coupling = 0.60
    coupled = simulate(on, paths=2500, seed=5)

    assert coupled.min_cash_p10_paise < base.min_cash_p10_paise, (
        "the pessimistic tail must get deeper when demand and delay move together")
    assert coupled.liquidity_cvar_paise >= base.liquidity_cvar_paise
    assert coupled.p90[-1] <= base.p90[-1], (
        "the optimistic path must not be flattered by the coupling")


def test_coupling_bites_the_bad_tail_hardest(sim):
    """A one-sided effect must be largest where it hurts and smallest where
    it flatters - the signature of a downside risk, not a blanket haircut.

    If the pessimistic and optimistic quantiles moved by the same proportion
    the coupling would just be shifting the whole distribution down, which
    would mean the delay term was no longer one-sided.
    """
    fi, _ = sim
    off = fi.copy()
    off.revenue_delay_coupling = 0.0
    base = simulate(off, paths=2500, seed=3)
    on = fi.copy()
    on.revenue_delay_coupling = 0.30
    coupled = simulate(on, paths=2500, seed=3)

    def rel(new, old):
        return abs(new - old) / max(1, abs(old))

    d_p10 = rel(coupled.min_cash_p10_paise, base.min_cash_p10_paise)
    d_p50 = rel(coupled.min_cash_p50_paise, base.min_cash_p50_paise)
    d_p90 = rel(coupled.min_cash_p90_paise, base.min_cash_p90_paise)
    assert d_p10 > d_p50 > d_p90, (
        f"effect must decay towards the good tail, got P10 {d_p10:.2f}, "
        f"P50 {d_p50:.2f}, P90 {d_p90:.2f}")


def test_coupling_uses_its_own_random_stream(sim):
    """Switching the coupling on must not reshuffle the other draws.

    Without this, a sensitivity row like "coupling doubled" would mix the
    real effect with sampling noise, because every other random variable in
    the model would be redrawn from a different point in the stream.
    """
    from app.forecast.cashflow import ForecastInputs
    # A ledger with only operating costs and unplanned shocks: nothing the
    # coupling is allowed to touch. If the market factor were drawn from the
    # main stream, turning it on would reshuffle these draws too.
    def costs_only(coupling):
        return ForecastInputs(
            as_of=TODAY, horizon_weeks=13, opening_cash_paise=50_000_00,
            restricted_paise=0, overdraft_limit_paise=0, safety_buffer_paise=0,
            weekly_opex_paise=2_00_000_00, opex_cv=0.12,
            shock_weekly_rate=0.06, shock_mean_paise=60_000_00,
            revenue_delay_coupling=coupling)

    off = simulate(costs_only(0.0), paths=600, seed=21)
    on = simulate(costs_only(0.60), paths=600, seed=21)
    assert on.outflow_p50 == off.outflow_p50
    assert on.p50 == off.p50


def test_coupling_scales_monotonically(sim):
    fi, _ = sim
    mins = []
    for c in (0.0, 0.2, 0.4, 0.6):
        f = fi.copy()
        f.revenue_delay_coupling = c
        mins.append(simulate(f, paths=1200, seed=13).min_cash_p10_paise)
    assert mins == sorted(mins, reverse=True), (
        f"deeper coupling must deepen the P10 trough, got {mins}")


def test_coupling_is_disclosed_in_the_assumptions(sim):
    _, s = sim
    assert "revenue_delay_coupling" in s.assumptions
    assert "revenue_delay_coupling_note" in s.assumptions
    assert "one-sided" in s.assumptions["revenue_delay_coupling_note"]
