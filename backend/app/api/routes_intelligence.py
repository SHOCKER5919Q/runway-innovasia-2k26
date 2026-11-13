"""Three-state architecture, forecasting, risk, health, twin and recommendations."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit, resolved_as_of
from app.core.enums import Role, StateType
from app.digital_twin.digital_twin_service import get_bundle
from app.models import (
    ActualSnapshot, Alert, BusinessState, PredictedSnapshot, Recommendation,
    SimulatedSnapshot, TwinEvent,
)

router = APIRouter(prefix="/api", tags=["intelligence"])
AsOf = Annotated[date, Depends(resolved_as_of)]


# ───────────────────────── three-state surface ───────────────────────

@router.get("/states/actual")
def state_actual(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    s, st = b.actual_snapshot, b.actual_state
    return jsonable({
        "state": {"type": "actual", "id": st.id, "version": st.version,
                  "as_of": st.as_of_date.isoformat(),
                  "created_at": st.created_at.isoformat(),
                  "ledger_fingerprint": st.ledger_fingerprint,
                  "engine_version": st.engine_version, "trigger": st.trigger},
        "definition": ("What is actually recorded, reconstructed from the reconciled "
                       "ledger. No prediction and no assumption appears in these figures."),
        "cash": money(s.cash_paise), "restricted": money(s.restricted_paise),
        "committed": money(s.committed_paise),
        "available_liquidity": money(s.available_liquidity_paise),
        "overdraft_headroom": money(s.overdraft_headroom_paise),
        "receivables": money(s.receivables_paise),
        "receivables_overdue": money(s.receivables_overdue_paise),
        "payables": money(s.payables_paise),
        "payables_overdue": money(s.payables_overdue_paise),
        "loan_outstanding": money(s.loan_outstanding_paise),
        "revenue_30d": money(s.revenue_30d_paise),
        "expense_30d": money(s.expense_30d_paise),
        "working_capital": money(s.working_capital_paise),
        "accounts": b.position.accounts,
        "committed_breakdown": b.position.committed_breakdown,
        "flow_30d": b.flow_30d, "working_capital_detail": b.working_capital,
        "data_quality": b.data_quality,
    })


@router.get("/states/predicted")
def state_predicted(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    p, st = b.predicted_snapshot, b.predicted_state
    s = b.simulation
    return jsonable({
        "state": {"type": "predicted", "id": st.id, "version": st.version,
                  "as_of": st.as_of_date.isoformat(),
                  "created_at": st.created_at.isoformat(),
                  "baseline_actual_state_id": p.baseline_actual_state_id,
                  "model_version": p.model_version, "method": p.method,
                  "seed": p.seed, "horizon_weeks": p.horizon_weeks},
        "definition": ("An evidence-based estimate of the future built from the actual "
                       "state. It is not a verified financial fact."),
        "quantile_convention": ("P10 is a pessimistic cash path, P50 the median and P90 "
                                "an optimistic one. These are simulation quantiles, not "
                                "confidence guarantees."),
        "series": s.dict() if s else None,
        "assumptions": p.assumptions_json,
        "sensitivity": b.sensitivity,
        "drivers": s.drivers if s else [],
    })


@router.get("/states/history")
def state_history(db: DbDep, ctx: Tenant,
                  state_type: str | None = Query(None), limit: int = Query(40, le=200)):
    from app.financial_states.state_manager import history
    return {"states": history(db, ctx.business_id, state_type, limit),
            "note": ("States are immutable. A new version supersedes but never replaces "
                     "the previous one, which is what makes forecast accuracy measurable.")}


@router.get("/states/reconcile")
def state_reconcile(db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.financial_states.state_manager import reconcile_forecasts
    r = reconcile_forecasts(db, ctx.business_id, as_of)
    db.commit()
    return jsonable({
        **r,
        "interpretation": _accuracy_interpretation(r),
        "method": ("Each stored forecast point is matched against the cash position "
                   "actually recorded for that week. Nothing is self-reported and "
                   "nothing is excluded for being inconvenient."),
    })


def _accuracy_interpretation(r: dict) -> str:
    rows = r.get("cash_forecast_by_horizon") or []
    if not rows:
        return ("No forecast has reached its target week yet. RUNWAY shows nothing "
                "rather than quoting an accuracy figure it has not measured.")
    near = [x for x in rows if x["horizon_weeks"] <= 4]
    far = [x for x in rows if x["horizon_weeks"] > 6]
    parts = []
    if near:
        cov = sum(x["p10_p90_coverage"] * x["n"] for x in near) / sum(x["n"] for x in near)
        parts.append(f"At horizons up to 4 weeks the P10-P90 band contained the actual "
                     f"outcome {cov:.0%} of the time against an 80% target.")
    if far:
        cov = sum(x["p10_p90_coverage"] * x["n"] for x in far) / sum(x["n"] for x in far)
        n = sum(x["n"] for x in far)
        parts.append(f"Beyond 6 weeks coverage falls to {cov:.0%} over only {n} "
                     f"observations, so the long-horizon band is both less reliable and "
                     f"too thinly measured to draw a conclusion from.")
    return " ".join(parts)


class CompareIn(BaseModel):
    source_state_id: str
    target_state_id: str


@router.post("/states/compare")
def state_compare(body: CompareIn, db: DbDep, ctx: Tenant):
    a = db.get(BusinessState, body.source_state_id)
    bst = db.get(BusinessState, body.target_state_id)
    for s in (a, bst):
        if not s or s.business_id != ctx.business_id:
            raise HTTPException(404, "State not found in this business")

    def series(st):
        if st.state_type == StateType.PREDICTED:
            sn = db.get(PredictedSnapshot, st.id)
            return (sn.series_json or {}) if sn else {}
        if st.state_type == StateType.SIMULATED:
            sn = db.get(SimulatedSnapshot, st.id)
            return ((sn.outputs_json or {}).get("scenario") or {}) if sn else {}
        sn = db.get(ActualSnapshot, st.id)
        return {"cash": sn.cash_paise} if sn else {}

    sa, sb = series(a), series(bst)
    return jsonable({
        "source": {"id": a.id, "type": a.state_type, "version": a.version,
                   "as_of": a.as_of_date.isoformat()},
        "target": {"id": bst.id, "type": bst.state_type, "version": bst.version,
                   "as_of": bst.as_of_date.isoformat()},
        "source_series": sa, "target_series": sb,
        "comparable": bool(sa.get("week_starts") and sb.get("week_starts")),
        "note": ("Two forecasts are only directly comparable when they share a horizon "
                 "and an as-of date. RUNWAY says so rather than overlaying them anyway."),
    })


# ────────────────────────── forecast & risk ──────────────────────────

@router.get("/forecast")
def forecast(db: DbDep, ctx: Tenant, as_of: AsOf):
    out = state_predicted(db, ctx, as_of)
    # state_predicted uses the light bundle, which skips sensitivity, so the
    # Cash Runway page always said "Not computed for this view". The full
    # bundle is normally already cached by the dashboard.
    if not out.get("sensitivity"):
        out["sensitivity"] = jsonable(get_bundle(db, ctx.business_id, as_of).sensitivity)
    return out


@router.get("/risk")
def risk(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of)
    s = b.simulation
    return jsonable({
        "as_of": as_of.isoformat(),
        "alerts": [{"code": f.code, "level": f.level, "title": f.title,
                    "what_happened": f.what_happened, "why_it_matters": f.why_it_matters,
                    "evidence": f.evidence, "impact": money(f.impact_paise),
                    "impact_date": f.impact_date.isoformat() if f.impact_date else None,
                    "recommended_action": f.recommended_action,
                    "if_ignored": f.if_ignored} for f in b.findings],
        "counts": {lvl: sum(1 for f in b.findings if f.level == lvl)
                   for lvl in ("critical", "warning", "watch", "info")},
        "metrics": {
            "liquidity_var": money(s.liquidity_var_paise) if s else None,
            "liquidity_cvar": money(s.liquidity_cvar_paise) if s else None,
            "expected_shortfall": money(s.expected_shortfall_paise) if s else None,
            "breach_probability": s.breach_probability if s else None,
            "negative_cash_probability": s.negative_cash_probability if s else None,
            "min_cash_p10": money(s.min_cash_p10_paise) if s else None,
            "var_confidence": (s.assumptions.get("var_confidence") if s else None),
            "definitions": {
                "liquidity_var": (s.assumptions.get("var_definition") if s else None),
                "liquidity_cvar": (s.assumptions.get("cvar_definition") if s else None)},
        },
        "stress_tests": b.stress,
        "sensitivity": b.sensitivity,
        "concentration": b.concentration,
        "correlation": b.correlation,
        "anomalies": b.anomalies,
        "risk_surface": _risk_surface(s) if s else None,
    })


def _risk_surface(s) -> dict:
    """A week x severity grid: how likely is cash to fall below each threshold."""
    buffer = s.safety_buffer_paise or 1
    levels = [("Below zero", 0), ("Below 25% of buffer", int(buffer * 0.25)),
              ("Below 50% of buffer", int(buffer * 0.5)),
              ("Below buffer", buffer), ("Below 150% of buffer", int(buffer * 1.5))]
    grid = []
    for label, thresh in levels:
        row = []
        for w in range(1, len(s.p50)):
            # Interpolate the empirical CDF from the stored quantiles.
            qs = [(0.10, s.p10[w]), (0.25, s.p25[w]), (0.50, s.p50[w]),
                  (0.75, s.p75[w]), (0.90, s.p90[w])]
            p = 0.0
            if thresh <= qs[0][1]:
                p = 0.10 * max(0.0, min(1.0, thresh / max(1, qs[0][1]))) if qs[0][1] > 0 else 0.0
            elif thresh >= qs[-1][1]:
                p = 1.0
            else:
                for (q1, v1), (q2, v2) in zip(qs, qs[1:]):
                    if v1 <= thresh <= v2:
                        p = q1 + (q2 - q1) * ((thresh - v1) / max(1, (v2 - v1)))
                        break
            row.append(round(float(p), 3))
        grid.append({"label": label, "threshold_paise": thresh, "by_week": row})
    return {"week_starts": s.week_starts[1:], "levels": grid,
            "method": ("Probabilities interpolated from the simulated quantile paths. "
                       "Read a cell as 'the chance cash is below this level in this week'.")}


@router.get("/health")
def health(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(), **b.health,
                     "working_capital": b.working_capital,
                     "concentration": b.concentration})


@router.get("/recommendations")
def recommendations(db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.api.routes_core import _rec_json
    b = get_bundle(db, ctx.business_id, as_of)
    # The engine regenerates recommendations on every build; the owner's
    # decision lives on the stored row. Without merging it back, pressing
    # Accept or Dismiss saved the status but the list never showed it.
    stored = {}
    for r in db.scalars(select(Recommendation).where(
            Recommendation.business_id == ctx.business_id)).all():
        if r.code not in stored or (stored[r.code].status == "open" and r.status != "open"):
            stored[r.code] = r
    recs = []
    for r in b.recommendations:
        j = _rec_json(r)
        row = stored.get(r.code)
        j["status"] = row.status if row else "open"
        j["decided_at"] = (row.updated_at.isoformat()
                           if row is not None and row.status in ("accepted", "dismissed", "done")
                           and getattr(row, "updated_at", None) else None)
        recs.append(j)
    order = {"open": 0, "accepted": 1, "done": 2, "dismissed": 3}
    recs.sort(key=lambda j: order.get(j["status"], 0))
    # What the approved actions would do, if the owner carries them out.
    # RUNWAY never moves money itself, so this is a projection (simulated),
    # not a change to the recorded books.
    def _st(r):
        return stored[r.code].status if stored.get(r.code) else "open"
    approved = [r for r in b.recommendations if _st(r) == "accepted"]
    done = [r for r in b.recommendations if _st(r) == "done"]
    lift_a = sum(max(0, r.expected_effect_paise or 0) for r in approved)
    lift_d = sum(max(0, r.expected_effect_paise or 0) for r in done)
    lift = lift_a + lift_d
    avail = b.position.available_liquidity_paise
    plan = {"approved": len(approved) + len(done), "in_progress": len(approved),
            "done": len(done), "codes": [r.code for r in approved + done],
            "in_progress_lift": money(lift_a), "done_lift": money(lift_d),
            "available_now": money(avail), "expected_lift": money(lift),
            "available_if_done": money(avail + lift),
            "note": ("Projected. Marked-done actions stay counted until the next bank "
                     "statement confirms the money; then they show in recorded cash.")}
    return jsonable({
        "as_of": as_of.isoformat(),
        "approved_plan": plan,
        "recommendations": recs,
        "ranking": {
            "method": "explainable linear score over five published terms",
            "terms": {"urgency": "how soon it stops mattering",
                      "impact": "cash effect relative to the safety buffer",
                      "confidence": "how well evidenced the trigger is",
                      "ease": "how easy it is for the owner to actually do",
                      "reversibility": "how recoverable it is if it turns out wrong"},
        },
        "guarantee": ("RUNWAY never executes a payment, applies for credit or changes a "
                      "contract. Every recommendation requires the owner's approval, and "
                      "borrowing is only ever offered with its cost shown beside the cost "
                      "of the shortfall it would cover."),
    })


class RecAction(BaseModel):
    status: str


@router.post("/recommendations/{code}/status")
def set_rec_status(code: str, body: RecAction, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    if body.status not in ("open", "accepted", "dismissed", "done"):
        raise HTTPException(422, "invalid status")
    row = db.scalar(select(Recommendation).where(
        Recommendation.business_id == ctx.business_id, Recommendation.code == code))
    if not row:
        raise HTTPException(404, "Recommendation not found")
    row.status = body.status
    audit(db, ctx, "recommendation.status", entity="recommendation", entity_id=row.id,
          detail={"code": code, "status": body.status})
    db.commit()
    return {"ok": True, "code": code, "status": body.status}


@router.post("/alerts/{alert_id}/acknowledge")
def ack_alert(alert_id: str, db: DbDep, ctx: Tenant):
    from datetime import datetime, timezone
    a = db.get(Alert, alert_id)
    if not a or a.business_id != ctx.business_id:
        raise HTTPException(404, "Alert not found")
    a.acknowledged_at = datetime.now(timezone.utc)
    audit(db, ctx, "alert.acknowledge", entity="alert", entity_id=a.id)
    db.commit()
    return {"ok": True, "alert_id": alert_id}


# ──────────────────────────── digital twin ───────────────────────────

@router.get("/twin/state")
def twin_state(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    s = b.simulation
    return jsonable({
        "as_of": as_of.isoformat(),
        "business": {"id": b.business.id, "name": b.business.name,
                     "industry": b.business.industry},
        "financial_state": {
            "cash": money(b.actual_snapshot.cash_paise),
            "available_liquidity": money(b.actual_snapshot.available_liquidity_paise),
            "restricted": money(b.actual_snapshot.restricted_paise),
            "committed": money(b.actual_snapshot.committed_paise),
            "receivables": money(b.actual_snapshot.receivables_paise),
            "payables": money(b.actual_snapshot.payables_paise),
            "loans": money(b.actual_snapshot.loan_outstanding_paise),
            "working_capital": money(b.actual_snapshot.working_capital_paise),
            "revenue_30d": money(b.actual_snapshot.revenue_30d_paise),
            "expense_30d": money(b.actual_snapshot.expense_30d_paise)},
        "customer_state": [c.dict() for c in b.behaviour],
        "supplier_state": [s_.dict() for s_ in b.supplier_profiles],
        "obligation_state": b.obligations,
        "operational_state": {
            "available": False,
            "missing": ["inventory levels", "purchase orders", "sales orders",
                        "production commitments", "branch-level activity"],
            "note": ("No inventory or order-book source is connected. RUNWAY leaves "
                     "these blank rather than inventing stock figures, and the "
                     "cash-conversion metric says so explicitly.")},
        "health": b.health,
        "forecast_summary": {
            "runway_weeks_p50": s.runway_weeks_p50, "runway_weeks_p10": s.runway_weeks_p10,
            "min_cash_p50": money(s.min_cash_p50_paise),
            "min_cash_p10": money(s.min_cash_p10_paise),
            "breach_probability": s.breach_probability} if s else None,
        "versions": {"actual": b.actual_state.version,
                     "predicted": b.predicted_state.version,
                     "ledger_fingerprint": b.actual_state.ledger_fingerprint,
                     "last_updated": b.actual_state.created_at.isoformat()},
        "data_quality": b.data_quality,
    })


@router.get("/twin/graph")
def twin_graph(db: DbDep, ctx: Tenant, as_of: AsOf,
               min_amount_paise: int = Query(0, ge=0)):
    from app.digital_twin.relationship_graph import build
    return jsonable(build(db, ctx.business_id, as_of, min_amount_paise=min_amount_paise))


@router.get("/twin/timeline")
def twin_timeline(db: DbDep, ctx: Tenant, as_of: AsOf,
                  past_days: int = Query(30, ge=0, le=365),
                  future_weeks: int = Query(13, ge=1, le=52)):
    from app.digital_twin.temporal_state import timeline
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable(timeline(db, ctx.business_id, as_of, past_days=past_days,
                             future_weeks=future_weeks, predictions=b.predictions))


@router.get("/twin/activity")
def twin_activity(db: DbDep, ctx: Tenant, limit: int = Query(60, le=300)):
    rows = db.scalars(select(TwinEvent).where(TwinEvent.business_id == ctx.business_id)
                      .order_by(TwinEvent.at.desc()).limit(limit)).all()
    return jsonable({"events": [{"id": e.id, "at": e.at.isoformat(), "kind": e.kind,
                                 "summary": e.summary, "state_id": e.state_id,
                                 "detail": e.detail_json} for e in rows]})


@router.post("/twin/refresh")
def twin_refresh(db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.digital_twin.digital_twin_service import invalidate
    from app.financial_states.state_manager import refresh
    ctx.require(Role.MANAGER)
    invalidate(ctx.business_id)
    a, p = refresh(db, ctx.business_id, as_of, trigger="manual_refresh", reuse=False)
    db.commit()
    audit(db, ctx, "twin.refresh", detail={"actual_version": a.version,
                                           "predicted_version": p.version})
    db.commit()
    return {"ok": True, "actual_version": a.version, "predicted_version": p.version}
