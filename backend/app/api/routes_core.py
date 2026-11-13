"""Dashboard, briefing, business settings and the demo controls."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit, resolved_as_of
from app.core.enums import Role
from app.core.money import format_inr
from app.digital_twin.digital_twin_service import get_bundle, invalidate

router = APIRouter(prefix="/api", tags=["core"])
AsOf = Annotated[date, Depends(resolved_as_of)]


@router.get("/overview")
def overview(db: DbDep, ctx: Tenant, as_of: AsOf):
    """Everything the landing dashboard needs, in one round trip."""
    b = get_bundle(db, ctx.business_id, as_of)
    s, a = b.simulation, b.actual_snapshot
    top_alert = b.findings[0] if b.findings else None
    return jsonable({
        "business": {"id": b.business.id, "name": b.business.name,
                     "industry": b.business.industry, "city": b.business.city,
                     "is_demo": b.business.is_demo,
                     "demo_scenario": b.business.demo_scenario,
                     "safety_buffer": money(b.business.safety_buffer_paise),
                     "role": ctx.role},
        "as_of": as_of.isoformat(),
        "headline": {
            "available_cash": money(a.available_liquidity_paise),
            "cash_in_hand": money(a.cash_paise),
            "restricted": money(a.restricted_paise),
            "committed": money(a.committed_paise),
            "overdraft_headroom": money(a.overdraft_headroom_paise),
            "receivables": money(a.receivables_paise),
            "receivables_overdue": money(a.receivables_overdue_paise),
            "receivables_invoice_count": sum(c.invoices_open for c in b.behaviour),
            "payables": money(a.payables_paise),
            "payables_overdue": money(a.payables_overdue_paise),
            "runway_weeks_p50": s.runway_weeks_p50 if s else None,
            "runway_weeks_p10": s.runway_weeks_p10 if s else None,
            "runway_censored": bool(s and s.runway_weeks_p50 >= s.horizon_weeks),
            "health_score": b.health["score"], "health_band": b.health["band"],
            "breach_probability": s.breach_probability if s else None,
            "first_breach_week": s.first_breach_week_p50 if s else None,
        },
        "forecast": {
            "week_starts": s.week_starts, "p10": s.p10, "p50": s.p50, "p90": s.p90,
            "inflow_p50": s.inflow_p50, "outflow_p50": s.outflow_p50,
            "safety_buffer_paise": s.safety_buffer_paise,
            "breach_prob_by_week": s.breach_prob_by_week,
            "paths": s.paths, "seed": s.seed,
        } if s else None,
        "ageing": b.ageing_ar,
        "obligations_next_30d": [i for i in b.obligations["items"] if i["days_away"] <= 30],
        "health": b.health,
        "top_alert": _alert_json(top_alert) if top_alert else None,
        "alerts_count": {lvl: sum(1 for f in b.findings if f.level == lvl)
                         for lvl in ("critical", "warning", "watch", "info")},
        "recommendations": [_rec_json(r) for r in b.recommendations[:4]],
        "flow_30d": b.flow_30d,
        "data_quality": b.data_quality,
        "state_refs": {
            "actual_version": b.actual_state.version,
            "predicted_version": b.predicted_state.version,
            "ledger_fingerprint": b.actual_state.ledger_fingerprint,
            "built_ms": b.built_ms,
            "engine_version": b.actual_state.engine_version,
        },
    })


def _alert_json(f) -> dict:
    return {"code": f.code, "level": f.level, "title": f.title,
            "what_happened": f.what_happened, "why_it_matters": f.why_it_matters,
            "evidence": f.evidence, "impact": money(f.impact_paise),
            "impact_date": f.impact_date.isoformat() if f.impact_date else None,
            "recommended_action": f.recommended_action, "if_ignored": f.if_ignored,
            "dedupe_key": f.dedupe_key}


def _rec_json(r) -> dict:
    return {"code": r.code, "title": r.title, "priority": r.priority,
            "score_terms": r.score_terms, "evidence": r.trigger_evidence,
            "expected_effect": money(r.expected_effect_paise),
            "expected_effect_text": r.expected_effect_text,
            "downside": r.downside_text, "action": r.required_action,
            "deadline": r.deadline.isoformat() if r.deadline else None,
            "confidence": r.confidence, "explanation": r.explanation,
            "requires_approval": r.requires_approval,
            "linked_scenario": r.linked_scenario, "tags": r.tags}


@router.get("/briefing")
def briefing(db: DbDep, ctx: Tenant, as_of: AsOf):
    """Today's financial briefing.

    Every sentence is assembled from the bundle, and each line carries the
    state it came from so a prediction is never read as a fact.
    """
    b = get_bundle(db, ctx.business_id, as_of)
    s, a = b.simulation, b.actual_snapshot
    hour_greeting = "Good morning"
    lines: list[dict] = []

    lines.append({"kind": "cash", "state": "actual", "icon": "wallet",
                  "text": (f"You have {format_inr(a.available_liquidity_paise)} of available "
                           f"operating cash. That is {format_inr(a.cash_paise)} in the bank "
                           f"less {format_inr(a.restricted_paise)} lien-marked and "
                           f"{format_inr(a.committed_paise)} already committed."),
                  "value": money(a.available_liquidity_paise)})

    if s:
        wk4 = s.p50[min(4, len(s.p50) - 1)]
        lines.append({"kind": "forecast", "state": "predicted", "icon": "trending",
                      "text": (f"In 30 days the median projection is {format_inr(wk4)}, "
                               f"with a pessimistic P10 of "
                               f"{format_inr(s.p10[min(4, len(s.p10)-1)])}."),
                      "value": money(wk4)})

    late = [c for c in b.behaviour if c.risk_band in ("high", "critical")
            and c.outstanding_paise > 0]
    if late:
        c = late[0]
        lines.append({"kind": "receivable", "state": "predicted", "icon": "user",
                      "text": (f"{c.name} is your slowest large payer, averaging "
                               f"{c.mean_delay_days:+.0f} days against terms with "
                               f"{format_inr(c.outstanding_paise)} open."),
                      "value": money(c.outstanding_paise),
                      "link": {"type": "customer", "id": c.counterparty_id}})

    upcoming = [o for o in b.obligations["items"] if 0 <= o["days_away"] <= 10]
    if upcoming:
        big = max(upcoming, key=lambda o: o["amount_paise"])
        lines.append({"kind": "obligation", "state": "actual", "icon": "calendar",
                      "text": (f"{big['label']} of {format_inr(big['amount_paise'])} is due "
                               f"in {big['days_away']} days."),
                      "value": money(big["amount_paise"])})

    if s and s.first_breach_week_p50:
        wk = s.first_breach_week_p50
        lines.append({"kind": "risk", "state": "predicted", "icon": "alert",
                      "text": (f"Your P10 path crosses the "
                               f"{format_inr(s.safety_buffer_paise)} safety buffer in week "
                               f"{wk} ({s.week_starts[wk]}). "
                               f"{s.breach_probability:.0%} of simulated paths breach it."),
                      "value": money(s.min_cash_p10_paise)})

    top = b.recommendations[0] if b.recommendations else None
    action = None
    if top:
        action = {"title": top.title, "action": top.required_action,
                  "why": top.expected_effect_text, "code": top.code,
                  "deadline": top.deadline.isoformat() if top.deadline else None}

    return jsonable({
        "as_of": as_of.isoformat(),
        "greeting": f"{hour_greeting}, {ctx.user.full_name.split()[0]}",
        "subtitle": f"Here is your {b.business.name} financial briefing.",
        "lines": lines,
        "recommended_action": action,
        "secondary_actions": [{"title": r.title, "code": r.code}
                              for r in b.recommendations[1:4]],
        "health": {"score": b.health["score"], "band": b.health["band"]},
        "data_quality": b.data_quality,
        "provenance": ("Every figure above is computed by the RUNWAY engine from this "
                       "workspace's ledger. Lines marked 'predicted' are model estimates "
                       "with uncertainty, not recorded facts."),
    })


class SettingsIn(BaseModel):
    safety_buffer_paise: int | None = Field(default=None, ge=0)
    target_runway_weeks: float | None = Field(default=None, ge=0, le=104)
    max_customer_concentration: float | None = Field(default=None, ge=0, le=1)
    max_borrowing_apr: float | None = Field(default=None, ge=0, le=1)
    min_order_margin: float | None = Field(default=None, ge=0, le=1)
    risk_appetite: str | None = None
    locale: str | None = None
    name: str | None = None


@router.get("/business")
def get_business(db: DbDep, ctx: Tenant):
    b = ctx.business
    return jsonable({
        "id": b.id, "name": b.name, "legal_name": b.legal_name, "industry": b.industry,
        "gstin": b.gstin, "city": b.city, "state_code": b.state_code,
        "msme_class": b.msme_class, "udyam_number": b.udyam_number,
        "is_demo": b.is_demo, "demo_scenario": b.demo_scenario,
        "policies": {
            "safety_buffer": money(b.safety_buffer_paise),
            "target_runway_weeks": b.target_runway_weeks,
            "max_customer_concentration": b.max_customer_concentration,
            "max_borrowing_apr": b.max_borrowing_apr,
            "min_order_margin": b.min_order_margin,
            "risk_appetite": b.risk_appetite},
        "locale": b.locale, "role": ctx.role, "settings": b.settings_json,
    })


@router.patch("/business")
def update_business(body: SettingsIn, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    changed = {}
    for field, value in body.model_dump(exclude_none=True).items():
        if field == "risk_appetite" and value not in ("conservative", "balanced", "aggressive"):
            raise HTTPException(422, "risk_appetite must be conservative, balanced or aggressive")
        setattr(ctx.business, field, value)
        changed[field] = value
    audit(db, ctx, "business.update", entity="business", entity_id=ctx.business_id,
          detail=changed)
    db.commit()
    invalidate(ctx.business_id)
    return get_business(db, ctx)


@router.get("/demo/scenarios")
def demo_scenarios():
    from app.seed.profiles import SCENARIOS
    return {"scenarios": [{"key": k, "label": v.label, "summary": v.summary,
                           "narrative": v.narrative} for k, v in SCENARIOS.items()],
            "note": ("Switching a scenario regenerates the entire synthetic workspace "
                     "with a different set of payment behaviours and shocks. Every "
                     "module recomputes from the new ledger.")}


class SwitchIn(BaseModel):
    scenario: str
    as_of: str | None = None


@router.post("/demo/switch")
def demo_switch(body: SwitchIn, db: DbDep, ctx: Tenant):
    """Regenerate the demo workspace under a different scenario."""
    from app.seed.profiles import SCENARIOS
    from app.seed.seed import seed
    if not ctx.business.is_demo:
        raise HTTPException(400, "Scenario switching is only available in the demo workspace")
    ctx.require(Role.MANAGER)
    if body.scenario not in SCENARIOS:
        raise HTTPException(422, f"unknown scenario '{body.scenario}'")
    when = date.fromisoformat(body.as_of) if body.as_of else date.today()
    db.commit()
    result = seed(body.scenario, reset=False, today=when, verbose=False)
    invalidate()
    return {"ok": True, "scenario": body.scenario,
            "label": SCENARIOS[body.scenario].label,
            "narrative": SCENARIOS[body.scenario].narrative,
            "businesses": [{"id": x["id"], "name": x["name"],
                            "transactions": x["transactions"], "invoices": x["invoices"]}
                           for x in result["businesses"]],
            "note": "Sign-in sessions remain valid; business ids have changed, so reload."}


@router.get("/accountant/portfolio")
def accountant_portfolio(db: DbDep, ctx: Tenant, as_of: AsOf):
    """Multi-business view for a CA. Exception-based, not a wall of numbers."""
    from sqlalchemy import select as _s
    from app.models import Business, Membership
    if not ctx.user.is_accountant:
        raise HTTPException(403, "This workspace is for accountant accounts")
    rows = db.scalars(_s(Membership).where(Membership.user_id == ctx.user.id)).all()
    out = []
    for m in rows:
        biz = db.get(Business, m.business_id)
        if not biz:
            continue
        b = get_bundle(db, biz.id, as_of, heavy=False)
        crit = [f for f in b.findings if f.level in ("critical", "warning")]
        out.append({
            "business": {"id": biz.id, "name": biz.name, "industry": biz.industry,
                         "city": biz.city, "role": m.role},
            "health": {"score": b.health["score"], "band": b.health["band"]},
            "cash": money(b.actual_snapshot.available_liquidity_paise),
            "receivables": money(b.actual_snapshot.receivables_paise),
            "receivables_overdue": money(b.actual_snapshot.receivables_overdue_paise),
            "payables": money(b.actual_snapshot.payables_paise),
            "runway_weeks_p50": b.simulation.runway_weeks_p50 if b.simulation else None,
            "runway_weeks_p10": b.simulation.runway_weeks_p10 if b.simulation else None,
            "breach_probability": b.simulation.breach_probability if b.simulation else None,
            "exceptions": [{"level": f.level, "title": f.title} for f in crit[:5]],
            "exception_count": len(crit),
            "unreconciled": b.data_quality["unreconciled_count"],
            "data_quality": b.data_quality["score"],
            "msmed_breached": money(b.msmed["already_breached_paise"]),
            "next_gst": next((i for i in b.obligations["items"]
                              if i["kind"] == "gst" and not i["overdue"]), None),
        })
    out.sort(key=lambda r: (r["health"]["score"], -r["exception_count"]))
    return jsonable({
        "as_of": as_of.isoformat(), "clients": out,
        "summary": {
            "clients": len(out),
            "needing_attention": sum(1 for r in out if r["exception_count"] > 0),
            "total_receivables": money(sum(r["receivables"]["paise"] for r in out)),
            "total_overdue": money(sum(r["receivables_overdue"]["paise"] for r in out)),
        },
        "note": ("Access is granted per business by the owner and is revocable. "
                 "Only businesses that have granted you access appear here."),
    })
