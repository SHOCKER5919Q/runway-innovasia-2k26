"""The Master Financial State Engine.

Coordinates the three states mandated by the architecture:

  ACTUAL     reconstructed from the reconciled ledger - what *is*
  PREDICTED  forecast from an actual baseline - what is *likely*
  SIMULATED  a scenario branched off a baseline pair - what *could be*

Invariants enforced here and asserted in ``tests/test_three_state.py``:

1. Every state is immutable once written and carries a monotonic version.
2. A predicted state names the actual state it was built from; a simulated
   state names both. Those pointers are never rewritten, so an old scenario
   stays comparable against the baseline it was actually run on.
3. Superseding never deletes. Old forecasts remain queryable, which is the
   only way forecast accuracy can be measured honestly.
4. No simulated figure is ever written to a ledger table.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.enums import (
    Direction, Evidence, InvoiceKind, InvoiceStatus, StateType,
)
from app.models import (
    ActualSnapshot, Alert, BusinessState, Business, ForecastPoint, Invoice,
    Loan, PaymentPrediction, PredictedSnapshot, Recommendation, Scenario,
    SimulatedSnapshot, StateComparison, Transaction, TwinEvent, _uid,
)

ENGINE_VERSION = "0.9.0"


# ───────────────────────────── helpers ───────────────────────────────

def ledger_fingerprint(db, business_id: str, as_of: date) -> str:
    """Hash of the ledger's material contents.

    Two actual states with the same fingerprint describe the same financial
    reality, so the engine can skip recomputation and - more importantly -
    a forecast can prove which ledger it was built from.
    """
    row = db.execute(
        select(func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount_paise), 0),
               func.max(Transaction.updated_at))
        .where(Transaction.business_id == business_id, Transaction.value_date <= as_of)).one()
    inv = db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.settled_paise), 0),
               func.coalesce(func.sum(Invoice.total_paise), 0))
        .where(Invoice.business_id == business_id, Invoice.issue_date <= as_of)).one()
    raw = f"{as_of}|{row[0]}|{row[1]}|{row[2]}|{inv[0]}|{inv[1]}|{inv[2]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


def _next_version(db, business_id: str, state_type: str) -> int:
    v = db.scalar(select(func.max(BusinessState.version)).where(
        BusinessState.business_id == business_id, BusinessState.state_type == state_type))
    return int(v or 0) + 1


def _supersede(db, business_id: str, state_type: str) -> None:
    db.execute(update(BusinessState)
               .where(BusinessState.business_id == business_id,
                      BusinessState.state_type == state_type,
                      BusinessState.status == "current")
               .values(status="superseded"))


def log_event(db, business_id: str, kind: str, summary: str,
              state_id: str | None = None, detail: dict | None = None) -> None:
    db.add(TwinEvent(business_id=business_id, kind=kind, summary=summary[:300],
                     state_id=state_id, detail_json=detail or {}))


# ───────────────────────── ACTUAL STATE ──────────────────────────────

def build_actual(db, business_id: str, as_of: date, *, trigger: str = "manual",
                 reuse: bool = True) -> BusinessState:
    from app.analytics.cash import cash_position, flow_summary, working_capital

    fp = ledger_fingerprint(db, business_id, as_of)
    if reuse:
        existing = db.scalar(select(BusinessState).where(
            BusinessState.business_id == business_id,
            BusinessState.state_type == StateType.ACTUAL,
            BusinessState.status == "current",
            BusinessState.as_of_date == as_of,
            BusinessState.ledger_fingerprint == fp))
        if existing:
            return existing

    pos = cash_position(db, business_id, as_of)
    wc = working_capital(db, business_id, as_of)
    f30 = flow_summary(db, business_id, as_of, 30)

    ar_rows = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                               InvoiceStatus.WRITTEN_OFF]))).all()
    ap_rows = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                               InvoiceStatus.WRITTEN_OFF]))).all()
    ar = sum(i.outstanding_paise for i in ar_rows)
    ar_over = sum(i.outstanding_paise for i in ar_rows if i.due_date < as_of)
    ap = sum(i.outstanding_paise for i in ap_rows)
    ap_over = sum(i.outstanding_paise for i in ap_rows if i.due_date < as_of)
    loans = sum(l.outstanding_paise for l in db.scalars(select(Loan).where(
        Loan.business_id == business_id, Loan.is_active.is_(True))).all())

    quality = data_quality(db, business_id, as_of)

    _supersede(db, business_id, StateType.ACTUAL)
    state = BusinessState(
        id=_uid(), business_id=business_id, state_type=StateType.ACTUAL,
        version=_next_version(db, business_id, StateType.ACTUAL), as_of_date=as_of,
        engine_version=ENGINE_VERSION, ledger_fingerprint=fp,
        data_quality_json=quality, status="current", trigger=trigger)
    db.add(state)
    db.flush()

    weekly_net = (f30["net_paise"] * 7) // 30
    db.add(ActualSnapshot(
        state_id=state.id, business_id=business_id, as_of_date=as_of,
        cash_paise=pos.cash_paise, restricted_paise=pos.restricted_paise,
        committed_paise=pos.committed_paise,
        available_liquidity_paise=pos.available_liquidity_paise,
        overdraft_headroom_paise=pos.overdraft_headroom_paise,
        receivables_paise=ar, receivables_overdue_paise=ar_over,
        payables_paise=ap, payables_overdue_paise=ap_over,
        loan_outstanding_paise=loans,
        revenue_30d_paise=f30["inflow_paise"], expense_30d_paise=f30["outflow_paise"],
        net_burn_weekly_paise=weekly_net,
        working_capital_paise=wc["working_capital_paise"],
        detail_json={"position": pos.dict(), "working_capital": wc, "flow_30d": f30}))
    log_event(db, business_id, "actual_state_built",
              f"Actual state v{state.version} rebuilt from the ledger as of {as_of}",
              state.id, {"fingerprint": fp, "data_quality": quality["score"]})
    return state


def data_quality(db, business_id: str, as_of: date) -> dict:
    """How much of the picture is actually evidenced?"""
    total = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.business_id == business_id, Transaction.value_date <= as_of)) or 0
    verified = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.business_id == business_id, Transaction.value_date <= as_of,
        Transaction.evidence == Evidence.VERIFIED_ACTUAL)) or 0
    unrecon = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.business_id == business_id, Transaction.value_date <= as_of,
        Transaction.recon_status.in_(["unreconciled", "needs_review", "duplicate_suspect"]))) or 0
    uncat = db.scalar(select(func.count()).select_from(Transaction).where(
        Transaction.business_id == business_id, Transaction.value_date <= as_of,
        Transaction.category == "uncategorised")) or 0
    last_txn = db.scalar(select(func.max(Transaction.value_date)).where(
        Transaction.business_id == business_id))
    if isinstance(last_txn, str):
        last_txn = date.fromisoformat(last_txn)
    staleness = (as_of - last_txn).days if last_txn else 999

    verified_share = verified / total if total else 0.0
    recon_share = 1 - (unrecon / total) if total else 0.0
    cat_share = 1 - (uncat / total) if total else 0.0
    fresh = max(0.0, 1.0 - staleness / 14.0)
    score = round(100 * (0.30 * verified_share + 0.30 * recon_share +
                         0.20 * cat_share + 0.20 * fresh), 1)
    warnings = []
    if staleness > 3:
        warnings.append(f"No transactions imported for {staleness} days - the forecast "
                        f"is working from stale data.")
    if unrecon:
        warnings.append(f"{unrecon} transactions are unreconciled, needing review or "
                        f"flagged as possible duplicates.")
    if uncat:
        warnings.append(f"{uncat} transactions are uncategorised.")
    return {"score": score, "transactions": total,
            "verified_share": round(verified_share, 3),
            "reconciled_share": round(recon_share, 3),
            "categorised_share": round(cat_share, 3),
            "staleness_days": staleness,
            "last_transaction_date": last_txn.isoformat() if last_txn else None,
            "unreconciled_count": unrecon, "uncategorised_count": uncat,
            "warnings": warnings,
            "band": ("Good" if score >= 80 else "Adequate" if score >= 60 else "Weak")}


# ──────────────────────── PREDICTED STATE ────────────────────────────

def build_predicted(db, business_id: str, actual: BusinessState, *,
                    horizon_weeks: int | None = None, paths: int | None = None,
                    seed: int | None = None, trigger: str = "manual",
                    reuse: bool = True) -> tuple[BusinessState, Any]:
    from app.analytics.concentration import correlated_exposure
    from app.forecast.cashflow import build_inputs
    from app.forecast.monte_carlo import simulate
    from app.forecast.payment_delay import predict_open, train

    as_of = actual.as_of_date
    horizon = horizon_weeks or settings.forecast_horizon_weeks
    paths = paths or settings.monte_carlo_paths
    seed = seed if seed is not None else settings.monte_carlo_seed
    biz = db.get(Business, business_id)

    if reuse:
        prev = db.scalar(select(BusinessState).where(
            BusinessState.business_id == business_id,
            BusinessState.state_type == StateType.PREDICTED,
            BusinessState.status == "current").order_by(BusinessState.version.desc()))
        if prev and prev.source_state_id == actual.id:
            snap = db.get(PredictedSnapshot, prev.id)
            if snap and snap.horizon_weeks == horizon and snap.seed == seed:
                return prev, snap

    t0 = time.perf_counter()
    invoices = db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all()
    model = train(invoices, as_of)
    preds = predict_open(model, invoices, as_of)
    pred_map = {p["invoice_id"]: p for p in preds}

    fi = build_inputs(db, business_id, as_of, horizon_weeks=horizon, predictions=pred_map,
                      safety_buffer_paise=biz.safety_buffer_paise, industry=biz.industry)
    corr = correlated_exposure(db, business_id, as_of)
    if corr.get("available") and corr.get("mean_pairwise_r") is not None:
        fi.delay_correlation = float(min(0.9, max(0.0, corr["mean_pairwise_r"])))
        fi.assumptions["delay_correlation_source"] = (
            f"estimated from {len(corr.get('customers', []))} customers' monthly delay "
            f"series (mean pairwise r = {corr['mean_pairwise_r']})")
    else:
        fi.assumptions["delay_correlation_source"] = (
            f"default 0.25 - {corr.get('reason', 'insufficient history to estimate')}")

    sim = simulate(fi, paths=paths, seed=seed, confidence=settings.var_confidence)

    _supersede(db, business_id, StateType.PREDICTED)
    state = BusinessState(
        id=_uid(), business_id=business_id, state_type=StateType.PREDICTED,
        version=_next_version(db, business_id, StateType.PREDICTED), as_of_date=as_of,
        source_state_id=actual.id, engine_version=ENGINE_VERSION,
        ledger_fingerprint=actual.ledger_fingerprint,
        data_quality_json=actual.data_quality_json, status="current", trigger=trigger)
    db.add(state)
    db.flush()

    snap = PredictedSnapshot(
        state_id=state.id, business_id=business_id, baseline_actual_state_id=actual.id,
        model_version=f"{model.version}|cashflow-mc-1.3.0", horizon_weeks=horizon,
        method="ledger-driven Monte Carlo with single-factor correlated delays",
        seed=seed,
        runway_weeks_p50=sim.runway_weeks_p50, runway_weeks_p10=sim.runway_weeks_p10,
        min_cash_p50_paise=sim.min_cash_p50_paise, min_cash_p10_paise=sim.min_cash_p10_paise,
        first_breach_week=sim.first_breach_week_p50,
        breach_probability=sim.breach_probability,
        liquidity_var_paise=sim.liquidity_var_paise,
        liquidity_cvar_paise=sim.liquidity_cvar_paise,
        assumptions_json={**sim.assumptions,
                          "payment_delay_model": model.metrics,
                          "compute_ms": int((time.perf_counter() - t0) * 1000)},
        series_json=sim.dict())
    db.add(snap)

    # Flatten for backtesting: these rows are later matched against actuals.
    for w in range(1, horizon + 1):
        db.add(ForecastPoint(
            business_id=business_id, predicted_state_id=state.id, created_on=as_of,
            target_week_start=date.fromisoformat(sim.week_starts[w]), horizon_weeks=w,
            metric="closing_cash", p10_paise=sim.p10[w], p50_paise=sim.p50[w],
            p90_paise=sim.p90[w]))
    for p in preds:
        db.add(PaymentPrediction(
            business_id=business_id, invoice_id=p["invoice_id"], predicted_state_id=state.id,
            model_version=p["model_version"],
            predicted_delay_days_p50=p["predicted_delay_days_p50"],
            predicted_delay_days_p10=p["predicted_delay_days_p10"],
            predicted_delay_days_p90=p["predicted_delay_days_p90"],
            predicted_pay_date=date.fromisoformat(p["predicted_pay_date"]),
            prob_within_7=p["prob_within_7"], prob_within_15=p["prob_within_15"],
            prob_within_30=p["prob_within_30"], prob_default=p["prob_default"],
            confidence=p["confidence"], drivers_json=p["drivers"]))
    log_event(db, business_id, "forecast_generated",
              f"Predicted state v{state.version}: runway P50 {sim.runway_weeks_p50}w, "
              f"breach probability {sim.breach_probability:.0%}",
              state.id, {"paths": paths, "seed": seed, "horizon_weeks": horizon})
    return state, snap


# ──────────────────────── SIMULATED STATE ────────────────────────────

def run_scenario(db, scenario: Scenario, *, actual: BusinessState,
                 predicted: BusinessState, paths: int | None = None,
                 seed: int | None = None) -> tuple[BusinessState, SimulatedSnapshot, dict]:
    """Evaluate a scenario against a fixed baseline pair.

    The baseline is passed in rather than looked up, so re-running a saved
    scenario reproduces the comparison it was created against even after the
    ledger has moved on.
    """
    from app.digital_twin.scenario_engine import apply_scenario
    from app.forecast.monte_carlo import simulate

    paths = paths or settings.monte_carlo_paths
    seed = seed if seed is not None else settings.monte_carlo_seed
    base_snap = db.get(PredictedSnapshot, predicted.id)
    if base_snap is None:
        raise ValueError("baseline predicted snapshot is missing")

    fi = _inputs_from_snapshot(db, scenario.business_id, actual, base_snap)
    baseline_sim = simulate(fi, paths=paths, seed=seed)   # common random numbers
    scen_fi, extras = apply_scenario(fi, scenario.kind, scenario.parameters_json or {},
                                     actual.as_of_date)
    scen_sim = simulate(scen_fi, paths=paths, seed=seed)

    state = BusinessState(
        id=_uid(), business_id=scenario.business_id, state_type=StateType.SIMULATED,
        version=_next_version(db, scenario.business_id, StateType.SIMULATED),
        as_of_date=actual.as_of_date, source_state_id=predicted.id,
        engine_version=ENGINE_VERSION, ledger_fingerprint=actual.ledger_fingerprint,
        data_quality_json=actual.data_quality_json, status="current",
        trigger=f"scenario:{scenario.kind}")
    db.add(state)
    db.flush()

    peak_wc = max(0, -min(scen_sim.min_cash_p50_paise, 0)) + max(
        0, extras.get("cash_out_before_cash_in_paise", 0))
    snap = SimulatedSnapshot(
        state_id=state.id, business_id=scenario.business_id, scenario_id=scenario.id,
        baseline_actual_state_id=actual.id, baseline_predicted_state_id=predicted.id,
        parameters_json=scenario.parameters_json or {},
        outputs_json={"scenario": scen_sim.dict(), "baseline": baseline_sim.dict(),
                      "economics": extras},
        runway_weeks_p50=scen_sim.runway_weeks_p50,
        min_cash_p50_paise=scen_sim.min_cash_p50_paise,
        min_cash_p10_paise=scen_sim.min_cash_p10_paise,
        peak_wc_requirement_paise=peak_wc,
        breach_probability=scen_sim.breach_probability,
        expected_profit_paise=int(extras.get("expected_profit_paise", 0)),
        financing_cost_paise=int(extras.get("financing_cost_paise",
                                            extras.get("total_cost_paise", 0))),
        seed=seed)
    db.add(snap)
    scenario.last_run_state_id = state.id
    comparison = compare_simulations(baseline_sim, scen_sim, extras)
    db.add(StateComparison(
        id=_uid(), business_id=scenario.business_id, source_state_id=predicted.id,
        target_state_id=state.id, comparison_type="predicted_vs_simulated",
        metrics_json=comparison))
    log_event(db, scenario.business_id, "scenario_run",
              f"Scenario '{scenario.name}' run: runway {baseline_sim.runway_weeks_p50}w -> "
              f"{scen_sim.runway_weeks_p50}w", state.id,
              {"scenario_id": scenario.id, "kind": scenario.kind})
    return state, snap, {"scenario": scen_sim.dict(), "baseline": baseline_sim.dict(),
                         "economics": extras, "comparison": comparison}


def _inputs_from_snapshot(db, business_id: str, actual: BusinessState,
                          snap: PredictedSnapshot):
    """Rebuild the forecast inputs that produced a predicted snapshot.

    Rebuilt rather than stored verbatim because the inputs contain hundreds
    of invoice references; the ledger fingerprint on the state proves the
    rebuild is from the same data.
    """
    from app.forecast.cashflow import build_inputs
    biz = db.get(Business, business_id)
    preds = {p.invoice_id: {
        "predicted_pay_date": p.predicted_pay_date.isoformat(),
        "sigma_days": max(1.0, (p.predicted_delay_days_p90 - p.predicted_delay_days_p10) / 2.5631),
        "predicted_delay_days_p50": p.predicted_delay_days_p50,
    } for p in db.scalars(select(PaymentPrediction).where(
        PaymentPrediction.predicted_state_id == snap.state_id)).all()}
    fi = build_inputs(db, business_id, actual.as_of_date,
                      horizon_weeks=snap.horizon_weeks, predictions=preds,
                      safety_buffer_paise=biz.safety_buffer_paise, industry=biz.industry)
    src = snap.assumptions_json or {}
    if "delay_correlation_rho" in src:
        fi.delay_correlation = float(src["delay_correlation_rho"])
    return fi


def compare_simulations(baseline, scenario, economics: dict | None = None) -> dict:
    """The counterfactual table: baseline vs scenario, metric by metric."""
    def row(label, b, s, unit="paise", better="higher"):
        delta = s - b
        return {"metric": label, "baseline": b, "scenario": s, "delta": delta,
                "unit": unit,
                "direction": ("improved" if (delta > 0) == (better == "higher") and delta != 0
                              else "worse" if delta != 0 else "unchanged")}
    rows = [
        row("Minimum cash (P50)", baseline.min_cash_p50_paise, scenario.min_cash_p50_paise),
        row("Minimum cash (P10)", baseline.min_cash_p10_paise, scenario.min_cash_p10_paise),
        row("Closing cash at horizon (P50)", baseline.p50[-1], scenario.p50[-1]),
        row("Runway (P50)", baseline.runway_weeks_p50, scenario.runway_weeks_p50, "weeks"),
        row("Runway (P10)", baseline.runway_weeks_p10, scenario.runway_weeks_p10, "weeks"),
        row("Probability of breaching the buffer", baseline.breach_probability,
            scenario.breach_probability, "probability", "lower"),
        row("Probability of negative cash", baseline.negative_cash_probability,
            scenario.negative_cash_probability, "probability", "lower"),
        row("Liquidity VaR (95%)", baseline.liquidity_var_paise,
            scenario.liquidity_var_paise, "paise", "lower"),
        row("Liquidity CVaR (95%)", baseline.liquidity_cvar_paise,
            scenario.liquidity_cvar_paise, "paise", "lower"),
    ]
    econ = economics or {}
    improved = sum(1 for r in rows if r["direction"] == "improved")
    worse = sum(1 for r in rows if r["direction"] == "worse")
    return {
        "rows": rows,
        "economics": econ,
        "net_cash_effect_paise": scenario.p50[-1] - baseline.p50[-1],
        "runway_delta_weeks": round(scenario.runway_weeks_p50 - baseline.runway_weeks_p50, 2),
        "breach_delta": round(scenario.breach_probability - baseline.breach_probability, 4),
        "verdict": ("improves liquidity" if improved > worse else
                    "worsens liquidity" if worse > improved else "broadly neutral"),
        "method": ("Both paths simulated with the same seed and therefore the same random "
                   "draws (common random numbers), so the difference is attributable to "
                   "the decision rather than to simulation noise."),
        "p50_baseline": baseline.p50, "p50_scenario": scenario.p50,
        "p10_baseline": baseline.p10, "p10_scenario": scenario.p10,
        "p90_baseline": baseline.p90, "p90_scenario": scenario.p90,
        "week_starts": baseline.week_starts,
    }


# ─────────────────── STATE RECONCILIATION (A vs P) ───────────────────

def reconcile_forecasts(db, business_id: str, as_of: date) -> dict:
    """Score past forecasts against what actually happened.

    This is the feedback loop that lets RUNWAY claim a track record instead
    of an accuracy number from a slide.
    """
    from app.analytics.cash import cash_position

    pts = db.scalars(select(ForecastPoint).where(
        ForecastPoint.business_id == business_id,
        ForecastPoint.target_week_start <= as_of,
        ForecastPoint.actual_paise.is_(None))).all()
    resolved = 0
    for p in pts:
        target = p.target_week_start
        actual = cash_position(db, business_id, target)
        p.actual_paise = actual.cash_paise - actual.restricted_paise
        p.resolved_at = datetime.now(timezone.utc)
        resolved += 1

    done = db.scalars(select(ForecastPoint).where(
        ForecastPoint.business_id == business_id,
        ForecastPoint.actual_paise.isnot(None))).all()
    by_h: dict[int, list] = {}
    for p in done:
        by_h.setdefault(p.horizon_weeks, []).append(p)

    horizons = []
    for h in sorted(by_h):
        rows = by_h[h]
        errs = [p.p50_paise - p.actual_paise for p in rows]
        n = len(errs)
        mae = sum(abs(e) for e in errs) / n
        denom = sum(abs(p.actual_paise) for p in rows) or 1
        cover = sum(1 for p in rows if p.p10_paise <= p.actual_paise <= p.p90_paise) / n
        horizons.append({
            "horizon_weeks": h, "n": n,
            "mae_paise": int(mae),
            "rmse_paise": int((sum(e * e for e in errs) / n) ** 0.5),
            "wape": round(sum(abs(e) for e in errs) / denom, 4),
            "bias_paise": int(sum(errs) / n),
            "p10_p90_coverage": round(cover, 3),
            "coverage_target": 0.80,
        })

    # Payment-date predictions versus realised settlements.
    pp = db.scalars(select(PaymentPrediction).where(
        PaymentPrediction.business_id == business_id,
        PaymentPrediction.actual_delay_days.is_(None))).all()
    pay_resolved = 0
    for p in pp:
        inv = db.get(Invoice, p.invoice_id)
        if inv and inv.settled_date and inv.settled_date <= as_of:
            p.actual_delay_days = float((inv.settled_date - inv.due_date).days)
            p.resolved_at = datetime.now(timezone.utc)
            pay_resolved += 1
    scored = db.scalars(select(PaymentPrediction).where(
        PaymentPrediction.business_id == business_id,
        PaymentPrediction.actual_delay_days.isnot(None))).all()
    pay_metrics = None
    if scored:
        e = [p.predicted_delay_days_p50 - p.actual_delay_days for p in scored]
        cov = sum(1 for p in scored
                  if p.predicted_delay_days_p10 <= p.actual_delay_days <= p.predicted_delay_days_p90)
        pay_metrics = {
            "n": len(e), "mae_days": round(sum(abs(x) for x in e) / len(e), 2),
            "bias_days": round(sum(e) / len(e), 2),
            "p10_p90_coverage": round(cov / len(e), 3),
        }

    return {
        "as_of": as_of.isoformat(),
        "newly_resolved_forecast_points": resolved,
        "newly_resolved_payment_predictions": pay_resolved,
        "cash_forecast_by_horizon": horizons,
        "payment_prediction_accuracy": pay_metrics,
        "available": bool(horizons or pay_metrics),
        "note": ("Accuracy is measured only on forecasts whose target week has already "
                 "passed. A freshly seeded workspace has nothing to score yet, and "
                 "RUNWAY reports that rather than inventing a figure."),
    }


# ─────────────────────────── orchestration ───────────────────────────

def refresh(db, business_id: str, as_of: date, *, trigger: str = "manual",
            reuse: bool = True) -> tuple[BusinessState, BusinessState]:
    """The state transition workflow: ledger -> actual -> predicted."""
    actual = build_actual(db, business_id, as_of, trigger=trigger, reuse=reuse)
    predicted, _ = build_predicted(db, business_id, actual, trigger=trigger, reuse=reuse)
    return actual, predicted


def current(db, business_id: str, state_type: str) -> BusinessState | None:
    return db.scalar(select(BusinessState).where(
        BusinessState.business_id == business_id, BusinessState.state_type == state_type,
        BusinessState.status == "current").order_by(BusinessState.version.desc()))


def history(db, business_id: str, state_type: str | None = None, limit: int = 40) -> list[dict]:
    q = select(BusinessState).where(BusinessState.business_id == business_id)
    if state_type:
        q = q.where(BusinessState.state_type == state_type)
    rows = db.scalars(q.order_by(BusinessState.created_at.desc()).limit(limit)).all()
    return [{"id": s.id, "state_type": s.state_type, "version": s.version,
             "as_of": s.as_of_date.isoformat(), "created_at": s.created_at.isoformat(),
             "source_state_id": s.source_state_id, "status": s.status,
             "trigger": s.trigger, "engine_version": s.engine_version,
             "ledger_fingerprint": s.ledger_fingerprint,
             "data_quality": (s.data_quality_json or {}).get("score")} for s in rows]


# ─────────────────── long-horizon cross-check ────────────────────

SECONDARY_HORIZON_WEEKS = 26

# Scenarios whose effect is systematically understated by a 13-week window,
# because they change *future sales* — whose cash cost (purchases, paid in
# roughly lead+terms days) lands inside the window while their cash benefit
# (collections, ~53 days out) largely lands outside it.
HORIZON_SENSITIVE_KINDS = {
    "revenue_shock", "cost_increase", "hiring", "equipment_purchase", "composite",
}


def long_horizon_check(db, business_id: str, as_of: date, kind: str, params: dict,
                       *, paths: int = 1500, seed: int | None = None) -> dict | None:
    """Re-run a scenario over 26 weeks and report what the 13-week view missed.

    A 13-week window is the right primary horizon: it is how far ahead an
    MSME owner can act, and beyond it the forecast is dominated by sales
    that do not exist yet. But for a scenario that changes the *run-rate*,
    that window is systematically biased — it sees the purchases and not
    the collections they pay for.

    Rather than hide the bias behind a disclaimer, this runs the same
    comparison over two quarters and returns both, so the owner can see
    whether a scenario that looks mild over 13 weeks is actually mild.

    Returns ``None`` for scenarios the window does not bias.
    """
    from app.core.config import settings as _s
    from app.digital_twin.scenario_engine import ScenarioError, apply_scenario
    from app.forecast.cashflow import build_inputs
    from app.forecast.monte_carlo import simulate

    if kind not in HORIZON_SENSITIVE_KINDS:
        return None
    seed = seed if seed is not None else _s.monte_carlo_seed
    biz = db.get(Business, business_id)
    try:
        fi = build_inputs(db, business_id, as_of,
                          horizon_weeks=SECONDARY_HORIZON_WEEKS,
                          safety_buffer_paise=biz.safety_buffer_paise,
                          industry=biz.industry)
        scen_fi, _ = apply_scenario(fi, kind, params, as_of)
    except (ScenarioError, Exception):
        return None

    base = simulate(fi, paths=paths, seed=seed)
    scen = simulate(scen_fi, paths=paths, seed=seed)

    short_w = settings.forecast_horizon_weeks
    def at(series, w):
        return series[min(w, len(series) - 1)]

    d13 = at(scen.p50, short_w) - at(base.p50, short_w)
    d26 = scen.p50[-1] - base.p50[-1]
    # Has the full cost only become visible in the second quarter?
    emerges = abs(d26) > abs(d13) * 1.25 and d26 < 0

    return {
        "horizon_weeks": SECONDARY_HORIZON_WEEKS,
        "paths": paths, "seed": seed,
        "week_starts": scen.week_starts,
        "baseline_p50": base.p50, "scenario_p50": scen.p50,
        "closing_delta_at_13w_paise": int(d13),
        "closing_delta_at_26w_paise": int(d26),
        "min_cash_p50_delta_paise": scen.min_cash_p50_paise - base.min_cash_p50_paise,
        "min_cash_p10_delta_paise": scen.min_cash_p10_paise - base.min_cash_p10_paise,
        "breach_delta": round(scen.breach_probability - base.breach_probability, 4),
        "effect_grows_beyond_13_weeks": bool(emerges),
        "interpretation": (
            f"Over 13 weeks this changes closing cash by "
            f"{d13/100:,.0f} rupees; over 26 weeks, {d26/100:,.0f}. "
            + ("Most of the impact lands in the second quarter, because the "
               "purchases are paid long before the collections they support "
               "arrive. Judge this decision on the 26-week view."
               if emerges else
               "The 13-week view already captures the bulk of the effect.")),
    }
