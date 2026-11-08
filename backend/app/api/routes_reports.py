"""Cash Health Passport and consented sharing."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit
from app.core.db import as_utc
from app.core.enums import Role
from app.core.money import format_inr
from app.digital_twin.digital_twin_service import get_bundle
from app.models import Consent, SharedReport, _uid

router = APIRouter(prefix="/api/reports", tags=["reports"])
AsOf = Annotated[date, Depends(today_param)]


def _passport(db, business_id: str, as_of: date) -> dict:
    from app.financial_states.state_manager import reconcile_forecasts
    b = get_bundle(db, business_id, as_of, heavy=False)
    acc = reconcile_forecasts(db, business_id, as_of)
    db.commit()
    s = b.simulation
    biz = b.business

    def section(key, label, value, basis, verification):
        return {"key": key, "label": label, "value": value, "basis": basis,
                "verification": verification}

    monthly_rev = b.flow_30d["inflow_paise"]
    sections = [
        section("liquidity", "Liquidity",
                {"available": money(b.actual_snapshot.available_liquidity_paise),
                 "cash": money(b.actual_snapshot.cash_paise),
                 "restricted": money(b.actual_snapshot.restricted_paise),
                 "overdraft_headroom": money(b.actual_snapshot.overdraft_headroom_paise)},
                "Reconciled bank and cash balances as of the report date.",
                "verified_actual"),
        section("revenue_consistency", "Revenue consistency",
                {"last_30d_inflow": money(monthly_rev),
                 "score": next(x["score"] for x in b.health["subscores"]
                               if x["key"] == "revenue_consistency")},
                "Monthly billed revenue variability over the available history.",
                "derived_from_verified_ledger"),
        section("receivables", "Receivables performance",
                {"total": money(b.ageing_ar["total_paise"]),
                 "overdue": money(b.ageing_ar["overdue_paise"]),
                 "overdue_share": b.ageing_ar["overdue_share"],
                 "buckets": b.ageing_ar["buckets"]},
                "Open sales invoices aged against their due dates.",
                "verified_actual"),
        section("payment_behaviour", "Customer payment behaviour",
                [{"customer": c.name, "mean_delay_days": c.mean_delay_days,
                  "reliability_score": c.reliability_score,
                  "settled_invoices": c.invoices_settled,
                  "risk_band": c.risk_band} for c in b.behaviour[:8]],
                "Settled invoices only. Open invoices are excluded because they carry "
                "no information about speed of payment.",
                "verified_actual"),
        section("obligations", "Financial obligations",
                {"next_45_days": money(b.coverage["total_paise"]),
                 "statutory": money(b.coverage["statutory_paise"]),
                 "coverage_ratio": b.coverage["coverage_ratio"],
                 "loan_outstanding": money(b.actual_snapshot.loan_outstanding_paise)},
                "Contractual and statutory obligations from the ledger. GST amounts are "
                "RUNWAY estimates, not filed figures.",
                "mixed_verified_and_estimated"),
        section("cashflow_forecast", "Forecast stability",
                {"runway_weeks_p50": s.runway_weeks_p50 if s else None,
                 "runway_weeks_p10": s.runway_weeks_p10 if s else None,
                 "min_cash_p10": money(s.min_cash_p10_paise) if s else None,
                 "breach_probability": s.breach_probability if s else None,
                 "horizon_weeks": s.horizon_weeks if s else None,
                 "paths": s.paths if s else None},
                "Monte Carlo simulation over the reconciled ledger with invoice-level "
                "payment predictions.",
                "model_prediction"),
        section("forecast_accuracy", "Measured forecast accuracy",
                acc.get("cash_forecast_by_horizon") or [],
                "Past forecasts scored against the cash positions actually recorded. "
                "Empty when no forecast has yet reached its target week.",
                "measured"),
        section("health", "Financial health indicator",
                {"score": b.health["score"], "band": b.health["band"],
                 "subscores": [{"label": x["label"], "score": x["score"],
                                "weight": x["weight"]} for x in b.health["subscores"]]},
                "RUNWAY's own transparent indicator. Methodology is published and "
                "configurable.",
                "derived_indicator"),
        section("concentration", "Counterparty concentration",
                {"top1_share": b.concentration["top1_share"],
                 "top3_share": b.concentration["top3_share"],
                 "hhi": b.concentration["counterparty_hhi"],
                 "effective_counterparties": b.concentration["effective_counterparties"]},
                "Herfindahl-Hirschman index over 12 months of billing.",
                "verified_actual"),
        section("data_coverage", "Data coverage and verification",
                b.data_quality,
                "What share of the ledger is verified, reconciled and current.",
                "measured"),
    ]
    return {
        "report_type": "RUNWAY Cash Health Passport",
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "business": {"name": biz.name, "legal_name": biz.legal_name,
                     "industry": biz.industry, "city": biz.city, "gstin": biz.gstin,
                     "msme_class": biz.msme_class, "udyam_number": biz.udyam_number,
                     "is_demo_data": biz.is_demo},
        "sections": sections,
        "state_refs": {"actual_version": b.actual_state.version,
                       "predicted_version": b.predicted_state.version,
                       "ledger_fingerprint": b.actual_state.ledger_fingerprint,
                       "engine_version": b.actual_state.engine_version},
        "declarations": [
            "This report is generated by RUNWAY from the business's own financial "
            "records. It is owned by the business and shared only with its consent.",
            "It is NOT a credit rating, NOT a credit score and NOT issued by a credit "
            "information company. No lender is obliged to recognise it.",
            "Figures marked 'model_prediction' are simulation output with stated "
            "uncertainty. Figures marked 'estimated' are derived by RUNWAY and have not "
            "been confirmed against a filed return or a third-party statement.",
            ("The underlying data in this workspace is SYNTHETIC and generated for "
             "demonstration. It does not describe a real business."
             if biz.is_demo else
             "The underlying data was supplied by the business through the sources "
             "listed under data coverage."),
        ],
    }


@router.get("/passport")
def passport(db: DbDep, ctx: Tenant, as_of: AsOf):
    return jsonable(_passport(db, ctx.business_id, as_of))


class ShareIn(BaseModel):
    recipient: str = Field(min_length=1, max_length=200)
    expires_in_days: int = Field(default=30, ge=1, le=365)
    purpose: str = "share_passport"


@router.post("/passport/share")
def share_passport(body: ShareIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Issue a shareable link under an explicit, revocable consent."""
    ctx.require(Role.OWNER)
    payload = _passport(db, ctx.business_id, as_of)
    consent = Consent(id=_uid(), business_id=ctx.business_id, purpose=body.purpose,
                      scope_json=["read:cash_health_passport"],
                      granted_by_user_id=ctx.user.id, grantee=body.recipient,
                      expires_at=datetime.now(timezone.utc) + timedelta(days=body.expires_in_days))
    db.add(consent)
    db.flush()
    rep = SharedReport(id=_uid(), business_id=ctx.business_id, consent_id=consent.id,
                       recipient=body.recipient, payload_json=jsonable(payload),
                       expires_at=consent.expires_at)
    db.add(rep)
    audit(db, ctx, "passport.share", entity="shared_report", entity_id=rep.id,
          detail={"recipient": body.recipient, "expires_in_days": body.expires_in_days})
    db.commit()
    return {"ok": True, "token": rep.token, "consent_id": consent.id,
            "url": f"/shared/{rep.token}",
            "expires_at": rep.expires_at.isoformat(),
            "recipient": body.recipient,
            "note": ("The recipient sees a snapshot taken now. Revoking the consent "
                     "disables the link immediately.")}


@router.get("/shared")
def list_shared(db: DbDep, ctx: Tenant):
    rows = db.scalars(select(SharedReport).where(
        SharedReport.business_id == ctx.business_id).order_by(
        SharedReport.created_at.desc())).all()
    return jsonable({"shares": [{
        "id": r.id, "token": r.token, "recipient": r.recipient,
        "created_at": r.created_at.isoformat(),
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
        "view_count": r.view_count,
        "active": r.revoked_at is None and (
            r.expires_at is None or as_utc(r.expires_at) > datetime.now(timezone.utc))}
        for r in rows]})


@router.post("/shared/{report_id}/revoke")
def revoke_share(report_id: str, db: DbDep, ctx: Tenant):
    ctx.require(Role.OWNER)
    r = db.get(SharedReport, report_id)
    if not r or r.business_id != ctx.business_id:
        raise HTTPException(404, "Shared report not found")
    r.revoked_at = datetime.now(timezone.utc)
    c = db.get(Consent, r.consent_id)
    if c:
        c.revoked_at = r.revoked_at
    audit(db, ctx, "passport.revoke", entity="shared_report", entity_id=r.id)
    db.commit()
    return {"ok": True, "revoked": True}


public_router = APIRouter(prefix="/public", tags=["public"])


@public_router.get("/shared/{token}")
def view_shared(token: str, db: DbDep):
    """Consented, unauthenticated view of a Cash Health Passport."""
    r = db.scalar(select(SharedReport).where(SharedReport.token == token))
    if not r:
        raise HTTPException(404, "This link is not valid")
    if r.revoked_at:
        raise HTTPException(410, "The business has revoked access to this report")
    if r.expires_at and as_utc(r.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(410, "This link has expired")
    r.view_count += 1
    db.commit()
    return {"report": r.payload_json, "recipient": r.recipient,
            "shared_at": r.created_at.isoformat(),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "notice": ("Shared by the business under a revocable consent. RUNWAY does "
                       "not sell or syndicate this data.")}
