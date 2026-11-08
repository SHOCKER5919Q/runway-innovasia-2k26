"""The statutory and contractual obligation calendar."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.core.enums import Evidence, ObligationKind
from app.models import Loan, Obligation

STATUTORY = {ObligationKind.GST, ObligationKind.TDS, ObligationKind.PF_ESI}
GST_FILING_DAY = 20   # GSTR-3B for the previous month


def calendar(db, business_id: str, as_of: date, days: int = 95) -> dict:
    end = as_of + timedelta(days=days)
    rows = db.scalars(select(Obligation).where(
        Obligation.business_id == business_id, Obligation.is_paid.is_(False),
        Obligation.due_date >= as_of - timedelta(days=30),
        Obligation.due_date <= end).order_by(Obligation.due_date)).all()

    items = [{
        "id": o.id, "kind": o.kind, "label": o.label,
        "due_date": o.due_date.isoformat(),
        "days_away": (o.due_date - as_of).days,
        "amount_paise": o.amount_paise,
        "evidence": o.evidence,
        "is_estimated": o.evidence in (Evidence.OWNER_ESTIMATE, Evidence.MODEL_PREDICTION),
        "statutory": o.kind in STATUTORY,
        "reserve_cash": o.reserve_cash,
        "overdue": o.due_date < as_of,
        "detail": o.detail_json,
    } for o in rows]

    for ln in db.scalars(select(Loan).where(Loan.business_id == business_id,
                                            Loan.is_active.is_(True))).all():
        cur = as_of.replace(day=1)
        for _ in range(days // 28 + 2):
            try:
                due = cur.replace(day=min(ln.emi_day, 28))
            except ValueError:
                break
            if as_of <= due <= end and not any(
                    i["kind"] == ObligationKind.LOAN_EMI and i["due_date"] == due.isoformat()
                    for i in items):
                items.append({
                    "id": f"loan-{ln.id}-{due.isoformat()}", "kind": ObligationKind.LOAN_EMI,
                    "label": f"{ln.lender} EMI", "due_date": due.isoformat(),
                    "days_away": (due - as_of).days, "amount_paise": ln.emi_paise,
                    "evidence": Evidence.VERIFIED_ACTUAL, "is_estimated": False,
                    "statutory": False, "reserve_cash": True,
                    "overdue": False, "detail": {"loan_id": ln.id, "rate": ln.annual_rate}})
            cur = (cur + timedelta(days=32)).replace(day=1)

    items.sort(key=lambda i: i["due_date"])
    total = sum(i["amount_paise"] for i in items if not i["overdue"])
    return {
        "as_of": as_of.isoformat(), "horizon_days": days, "items": items,
        "total_upcoming_paise": total,
        "statutory_paise": sum(i["amount_paise"] for i in items if i["statutory"]),
        "estimated_paise": sum(i["amount_paise"] for i in items if i["is_estimated"]),
        "overdue_paise": sum(i["amount_paise"] for i in items if i["overdue"]),
        "note": ("Items marked estimated are derived by RUNWAY from the ledger, not from "
                 "a filed return. Verify a GST liability on the GST portal before paying."),
    }


def coverage(db, business_id: str, as_of: date, horizon_days: int = 45,
             expected_inflow_paise: int | None = None) -> dict:
    """Can the business meet its obligations over the horizon?

    Three ratios, because they answer different questions:

    * ``coverage_ratio_cash_only`` - if nothing at all comes in.
    * ``coverage_ratio`` - including the P50 collections the forecast expects.
      This is the operationally meaningful one and the one the health score
      uses, because a business with Rs 1 crore of receivables arriving is not
      in distress merely because its bank balance is smaller than its bills.
    * ``with_overdraft_ratio`` - adding undrawn credit, which is borrowing,
      not cash.
    """
    from app.analytics.cash import cash_position
    pos = cash_position(db, business_id, as_of)
    cal = calendar(db, business_id, as_of, days=horizon_days)
    total = cal["total_upcoming_paise"] + cal["overdue_paise"]
    cash = pos.available_liquidity_paise
    expected = int(expected_inflow_paise or 0)
    return {
        "as_of": as_of.isoformat(), "horizon_days": horizon_days,
        "available_liquidity_paise": cash,
        "expected_collections_paise": expected,
        "total_paise": total,
        "statutory_paise": cal["statutory_paise"],
        "coverage_ratio_cash_only": round(cash / total, 3) if total else 99.0,
        "coverage_ratio": round((cash + expected) / total, 3) if total else 99.0,
        "shortfall_paise": max(0, total - cash - expected),
        "with_overdraft_ratio": round(
            (cash + expected + pos.overdraft_headroom_paise) / total, 3) if total else 99.0,
        "expected_collections_basis": ("P50 simulated collections over the horizon"
                                       if expected else "not supplied - cash only"),
    }


def next_gst_deadline(as_of: date) -> dict:
    """Next GSTR-3B date and the period it covers."""
    d = as_of.replace(day=GST_FILING_DAY)
    if d < as_of:
        d = (as_of.replace(day=1) + timedelta(days=32)).replace(day=GST_FILING_DAY)
    period_start = (d.replace(day=1) - timedelta(days=1)).replace(day=1)
    return {"due_date": d.isoformat(), "days_away": (d - as_of).days,
            "period": period_start.strftime("%B %Y"), "return": "GSTR-3B",
            "note": "Monthly filers. QRMP filers follow a different calendar."}
