"""The temporal twin: one ordered stream of financial events.

Past events are facts drawn from the ledger. Future events are a mixture of
contractual certainties (an EMI), statutory deadlines (GST) and model
predictions (a customer payment). Each carries its evidence class, so the
timeline can render certainty differently from expectation and nobody has to
guess which is which.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.core.enums import Direction, Evidence, InvoiceKind, InvoiceStatus
from app.models import Counterparty, Invoice, Loan, Obligation, Transaction


def timeline(db, business_id: str, as_of: date, *, past_days: int = 30,
             future_weeks: int = 13, predictions: dict | None = None,
             limit: int = 400) -> dict:
    parties = {c.id: c.name for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    events: list[dict] = []

    for t in db.scalars(select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.value_date >= as_of - timedelta(days=past_days),
            Transaction.value_date <= as_of).order_by(Transaction.value_date.desc())).all():
        events.append({
            "id": f"txn:{t.id}", "date": t.value_date.isoformat(), "tense": "past",
            "type": "payment_received" if t.direction == Direction.CREDIT else "payment_made",
            "label": (parties.get(t.counterparty_id) or t.narration[:60]),
            "detail": t.narration[:160],
            "amount_paise": t.signed_paise, "category": t.category,
            "evidence": t.evidence, "certainty": "actual",
            "recon_status": t.recon_status})

    horizon = as_of + timedelta(weeks=future_weeks)

    for inv in db.scalars(select(Invoice).where(
            Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
            Invoice.issue_date <= as_of,
            Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                                   InvoiceStatus.WRITTEN_OFF]))).all():
        if inv.outstanding_paise <= 0:
            continue
        p = (predictions or {}).get(inv.id)
        pay = date.fromisoformat(p["predicted_pay_date"]) if p else max(inv.due_date, as_of)
        if pay > horizon:
            continue
        events.append({
            "id": f"recv:{inv.id}", "date": pay.isoformat(), "tense": "future",
            "type": "payment_predicted",
            "label": f"{parties.get(inv.counterparty_id, 'Customer')} - {inv.invoice_no}",
            "detail": (f"Due {inv.due_date.isoformat()}; predicted "
                       f"{p['predicted_delay_days_p50']:+.0f} days against terms"
                       if p else f"Due {inv.due_date.isoformat()}"),
            "amount_paise": inv.outstanding_paise, "category": "customer_receipt",
            "evidence": Evidence.MODEL_PREDICTION, "certainty": "predicted",
            "confidence": p.get("confidence") if p else None,
            "range": ({"p10_date": (inv.due_date + timedelta(days=int(p["predicted_delay_days_p10"]))).isoformat(),
                       "p90_date": (inv.due_date + timedelta(days=int(p["predicted_delay_days_p90"]))).isoformat()}
                      if p else None),
            "due_date": inv.due_date.isoformat(),
            "overdue": inv.due_date < as_of})

    from app.analytics.payables import msmed_deadline
    cps = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    for inv in db.scalars(select(Invoice).where(
            Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
            Invoice.issue_date <= as_of,
            Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                                   InvoiceStatus.WRITTEN_OFF]))).all():
        if inv.outstanding_paise <= 0:
            continue
        cp = cps.get(inv.counterparty_id)
        dl = msmed_deadline(inv, cp)
        eff = min([d for d in (inv.due_date, dl) if d is not None])
        when = max(eff, as_of)
        if when > horizon:
            continue
        events.append({
            "id": f"pay:{inv.id}", "date": when.isoformat(), "tense": "future",
            "type": "supplier_payment_due",
            "label": f"{cp.name if cp else 'Supplier'} - {inv.invoice_no}",
            "detail": ("Statutory MSMED deadline" if dl and dl <= inv.due_date
                       else f"Contractual due date {inv.due_date.isoformat()}"),
            "amount_paise": -inv.outstanding_paise, "category": "supplier_payment",
            "evidence": Evidence.VERIFIED_ACTUAL, "certainty": "contractual",
            "statutory_deadline": dl.isoformat() if dl else None,
            "overdue": eff < as_of})

    for o in db.scalars(select(Obligation).where(
            Obligation.business_id == business_id, Obligation.is_paid.is_(False),
            Obligation.due_date >= as_of - timedelta(days=15),
            Obligation.due_date <= horizon)).all():
        events.append({
            "id": f"ob:{o.id}", "date": o.due_date.isoformat(),
            "tense": "future" if o.due_date >= as_of else "past",
            "type": "obligation_due", "label": o.label, "detail": o.kind,
            "amount_paise": -o.amount_paise, "category": o.kind,
            "evidence": o.evidence,
            "certainty": ("estimated" if o.evidence == Evidence.OWNER_ESTIMATE
                          else "contractual"),
            "overdue": o.due_date < as_of})

    for ln in db.scalars(select(Loan).where(Loan.business_id == business_id,
                                            Loan.is_active.is_(True))).all():
        cur = as_of.replace(day=1)
        for _ in range(future_weeks // 4 + 2):
            try:
                due = cur.replace(day=min(ln.emi_day, 28))
            except ValueError:
                break
            if as_of <= due <= horizon:
                events.append({
                    "id": f"emi:{ln.id}:{due}", "date": due.isoformat(), "tense": "future",
                    "type": "loan_emi", "label": f"{ln.lender} EMI",
                    "detail": f"{ln.kind} at {ln.annual_rate:.1%}",
                    "amount_paise": -ln.emi_paise, "category": "loan_emi",
                    "evidence": Evidence.VERIFIED_ACTUAL, "certainty": "contractual",
                    "overdue": False})
            cur = (cur + timedelta(days=32)).replace(day=1)

    events.sort(key=lambda e: (e["date"], -abs(e["amount_paise"])))
    future = [e for e in events if e["tense"] == "future"]

    weeks: dict[str, dict] = {}
    for e in future:
        d = date.fromisoformat(e["date"])
        wk = (d - timedelta(days=d.weekday())).isoformat()
        b = weeks.setdefault(wk, {"week_start": wk, "inflow_paise": 0, "outflow_paise": 0,
                                  "events": 0, "predicted_paise": 0, "contractual_paise": 0})
        if e["amount_paise"] >= 0:
            b["inflow_paise"] += e["amount_paise"]
        else:
            b["outflow_paise"] += -e["amount_paise"]
        b["events"] += 1
        key = "predicted_paise" if e["certainty"] == "predicted" else "contractual_paise"
        b[key] += abs(e["amount_paise"])
    for b in weeks.values():
        b["net_paise"] = b["inflow_paise"] - b["outflow_paise"]

    return {
        "as_of": as_of.isoformat(), "events": events[:limit],
        "truncated": len(events) > limit, "total_events": len(events),
        "weekly": [weeks[k] for k in sorted(weeks)],
        "legend": {
            "actual": "Recorded in the ledger and reconciled",
            "contractual": "A known commitment with a fixed date",
            "estimated": "Derived by RUNWAY, not confirmed by a filed document",
            "predicted": "A model estimate with an uncertainty range",
        },
    }
