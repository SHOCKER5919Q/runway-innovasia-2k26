"""Customer payment-behaviour intelligence and receivables ageing.

Everything here is computed from *settled* invoices only - an invoice that is
still open tells you nothing about how long that customer takes to pay, and
including it would bias every statistic optimistically.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from sqlalchemy import select, or_

from app.ledger.asof import outstanding_at, was_settled_by
from app.core.enums import InvoiceKind, InvoiceStatus
from app.models import Counterparty, Invoice

AGE_BUCKETS = [(0, 0, "Not due"), (1, 30, "1-30 days"), (31, 60, "31-60 days"),
               (61, 90, "61-90 days"), (91, 10_000, "90+ days")]
MIN_HISTORY = 3


@dataclass
class CustomerBehaviour:
    counterparty_id: str
    name: str
    sector: str | None
    region: str | None
    credit_days: int
    invoices_settled: int
    invoices_open: int
    lifetime_billed_paise: int
    revenue_share: float
    mean_delay_days: float
    median_delay_days: float
    p90_delay_days: float
    delay_sd: float
    on_time_rate: float               # settled within terms
    partial_payment_rate: float
    outstanding_paise: int
    overdue_paise: int
    oldest_overdue_days: int
    dso_days: float | None
    reliability_score: float          # 0..100
    risk_band: str                    # low | medium | high | critical
    evidence: list[str]
    data_confidence: float

    def dict(self) -> dict:
        return asdict(self)


def _delays(invoices: list[Invoice], as_of: date | None = None) -> list[float]:
    """Days late for invoices settled *by* ``as_of`` (a later payment is not
    yet known on that date, so it must not shape a past view)."""
    out = []
    for inv in invoices:
        if inv.settled_date and inv.status == InvoiceStatus.PAID and (
                as_of is None or inv.settled_date <= as_of):
            out.append(float((inv.settled_date - inv.due_date).days))
    return out


def _risk_band(reliability: float, overdue_share: float, oldest: int) -> str:
    if reliability < 35 or oldest > 90 or overdue_share > 0.7:
        return "critical"
    if reliability < 55 or oldest > 45 or overdue_share > 0.4:
        return "high"
    if reliability < 75 or oldest > 15:
        return "medium"
    return "low"


def customer_behaviour(db, business_id: str, as_of: date,
                       lookback_days: int = 540) -> list[CustomerBehaviour]:
    since = as_of - timedelta(days=lookback_days)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= since, Invoice.issue_date <= as_of)).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}

    by_cp: dict[str, list[Invoice]] = {}
    for inv in invs:
        by_cp.setdefault(inv.counterparty_id, []).append(inv)
    total_billed = sum(i.total_paise for i in invs) or 1

    results: list[CustomerBehaviour] = []
    for cp_id, rows in by_cp.items():
        cp = parties.get(cp_id)
        if cp is None:
            continue
        settled = [i for i in rows if was_settled_by(i, as_of)]
        open_rows = [i for i in rows if outstanding_at(i, as_of) > 0]
        delays = _delays(rows, as_of)
        n = len(delays)
        mean_d = statistics.fmean(delays) if n else float(0)
        med_d = statistics.median(delays) if n else 0.0
        sd = statistics.pstdev(delays) if n > 1 else 0.0
        p90 = sorted(delays)[int(0.9 * (n - 1))] if n else 0.0
        on_time = (sum(1 for d in delays if d <= 0) / n) if n else 0.0
        partial = (sum(1 for i in rows if i.first_payment_date and i.settled_date
                       and i.first_payment_date != i.settled_date) / len(rows)) if rows else 0.0

        outstanding = sum(outstanding_at(i, as_of) for i in open_rows)
        overdue_rows = [i for i in open_rows if i.due_date < as_of]
        overdue = sum(outstanding_at(i, as_of) for i in overdue_rows)
        oldest = max(((as_of - i.due_date).days for i in overdue_rows), default=0)

        # Days Sales Outstanding, Simple method: outstanding / avg daily billing
        window_billed = sum(i.total_paise for i in rows)
        daily = window_billed / max(1, min(lookback_days, (as_of - min(i.issue_date for i in rows)).days or 1))
        dso = round(outstanding / daily, 1) if daily > 0 else None

        # Reliability: punctuality (how late) blended with consistency (how
        # predictable) and discounted for current overdue exposure.
        punctual = max(0.0, 1.0 - max(0.0, mean_d) / 45.0)
        consistent = max(0.0, 1.0 - sd / 30.0)
        overdue_share = overdue / outstanding if outstanding else 0.0
        reliability = 100 * (0.55 * punctual + 0.25 * consistent + 0.20 * (1 - overdue_share))
        reliability = round(max(0.0, min(100.0, reliability)), 1)
        conf = min(1.0, n / 12.0) if n else 0.0

        ev = [f"{n} settled invoices analysed over {lookback_days} days"]
        if n:
            ev.append(f"mean {mean_d:+.1f} days vs due date, median {med_d:+.1f}, sd {sd:.1f}")
        if overdue:
            ev.append(f"{len(overdue_rows)} overdue invoices, oldest {oldest} days past due")
        if n < MIN_HISTORY:
            ev.append("too few settled invoices for a confident behaviour estimate")

        results.append(CustomerBehaviour(
            counterparty_id=cp_id, name=cp.name, sector=cp.sector, region=cp.region,
            credit_days=cp.credit_days, invoices_settled=len(settled), invoices_open=len(open_rows),
            lifetime_billed_paise=window_billed,
            revenue_share=round(window_billed / total_billed, 4),
            mean_delay_days=round(mean_d, 2), median_delay_days=round(med_d, 2),
            p90_delay_days=round(float(p90), 2), delay_sd=round(sd, 2),
            on_time_rate=round(on_time, 3), partial_payment_rate=round(partial, 3),
            outstanding_paise=outstanding, overdue_paise=overdue, oldest_overdue_days=oldest,
            dso_days=dso, reliability_score=reliability,
            risk_band=_risk_band(reliability, overdue_share, oldest),
            evidence=ev, data_confidence=round(conf, 2)))

    results.sort(key=lambda c: -c.outstanding_paise)
    return results


def ageing(db, business_id: str, as_of: date, kind: str = InvoiceKind.SALES) -> dict:
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == kind,
        Invoice.issue_date <= as_of,
        # Open on that date - including invoices paid only afterwards, so a
        # past as-of date is not rewritten by later payments.
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]),
        or_(Invoice.status != InvoiceStatus.PAID, Invoice.settled_date > as_of))).all()
    buckets = [{"lo": lo, "hi": hi, "label": lbl, "amount_paise": 0, "count": 0}
               for lo, hi, lbl in AGE_BUCKETS]
    total = 0
    for inv in invs:
        out = outstanding_at(inv, as_of)
        if out <= 0:
            continue
        total += out
        age = (as_of - inv.due_date).days
        idx = 0 if age <= 0 else next(i for i, (lo, hi, _) in enumerate(AGE_BUCKETS)
                                      if i > 0 and lo <= age <= hi)
        buckets[idx]["amount_paise"] += out
        buckets[idx]["count"] += 1
    for b in buckets:
        b["share"] = round(b["amount_paise"] / total, 4) if total else 0.0
    overdue = sum(b["amount_paise"] for b in buckets[1:])
    return {"as_of": as_of.isoformat(), "kind": kind, "total_paise": total,
            "overdue_paise": overdue,
            "overdue_share": round(overdue / total, 4) if total else 0.0,
            "buckets": buckets}


def collection_priority(db, business_id: str, as_of: date, predictions: dict[str, dict] | None = None,
                        limit: int = 25) -> list[dict]:
    """Rank open receivables by how much chasing them is worth.

    priority = outstanding x urgency x risk x (1 - already nearly due)
    Every term is reported so the ranking can be audited.
    """
    behaviour = {c.counterparty_id: c for c in customer_behaviour(db, business_id, as_of)}
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date <= as_of,
        # Open on that date - including invoices paid only afterwards, so a
        # past as-of date is not rewritten by later payments.
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]),
        or_(Invoice.status != InvoiceStatus.PAID, Invoice.settled_date > as_of))).all()
    rows = []
    max_out = max((outstanding_at(i, as_of) for i in invs), default=1) or 1
    for inv in invs:
        out = outstanding_at(inv, as_of)
        if out <= 0:
            continue
        b = behaviour.get(inv.counterparty_id)
        age = (as_of - inv.due_date).days
        size_term = out / max_out
        urgency = min(1.0, max(0.0, (age + 7) / 60.0))
        risk = {"low": 0.25, "medium": 0.55, "high": 0.8, "critical": 1.0}.get(
            b.risk_band if b else "medium", 0.55)
        pred = (predictions or {}).get(inv.id)
        score = round(100 * (0.45 * size_term + 0.30 * urgency + 0.25 * risk), 2)
        rows.append({
            "invoice_id": inv.id, "invoice_no": inv.invoice_no,
            "counterparty_id": inv.counterparty_id,
            "customer": b.name if b else "Unknown",
            "outstanding_paise": out, "total_paise": inv.total_paise,
            "issue_date": inv.issue_date.isoformat(), "due_date": inv.due_date.isoformat(),
            "days_past_due": age, "risk_band": b.risk_band if b else "unknown",
            "reliability_score": b.reliability_score if b else None,
            "predicted_pay_date": pred.get("predicted_pay_date") if pred else None,
            "predicted_delay_days": pred.get("predicted_delay_days_p50") if pred else None,
            "prob_within_15": pred.get("prob_within_15") if pred else None,
            "priority_score": score,
            "score_terms": {"size": round(size_term, 3), "urgency": round(urgency, 3),
                            "counterparty_risk": risk},
            "recommended_action": _action_for(age, b),
        })
    rows.sort(key=lambda r: -r["priority_score"])
    return rows[:limit]


def _action_for(days_past_due: int, b: CustomerBehaviour | None) -> str:
    if days_past_due < -3:
        return "No action needed yet - send the statement a week before the due date."
    if days_past_due <= 7:
        return "Send a polite payment reminder quoting the invoice number."
    if days_past_due <= 30:
        return "Call the accounts department and confirm a payment date in writing."
    if days_past_due <= 60:
        return ("Escalate to the buyer's finance head; put further credit supply on hold "
                "pending a written commitment.")
    return ("Issue a formal demand. If the buyer is a company, an MSME Samadhaan reference "
            "is available to registered micro and small enterprises.")
