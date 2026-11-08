"""Supplier obligations, early-payment discounts and MSMED/43B(h) exposure.

Statutory rules implemented (see ``docs/COMPLIANCE_NOTES.md`` for sources):

* **MSMED Act s.15** - a buyer must pay a registered *micro or small*
  enterprise within the agreed period, which cannot exceed **45 days**; with
  no written agreement the limit is **15 days**. Medium enterprises are not
  covered.
* **Income-tax s.43B(h)** - a payment to a micro/small enterprise beyond that
  window is not deductible in the year the expense was booked; unlike other
  43B items, paying before the return due date does not rescue it.

RUNWAY flags exposure. It does not give tax advice, and the flag is based on
the MSME classification recorded against the supplier, which the owner must
confirm.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from sqlalchemy import select

from app.core.enums import InvoiceKind, InvoiceStatus
from app.models import Counterparty, Invoice

MSMED_WITH_AGREEMENT_DAYS = 45
MSMED_NO_AGREEMENT_DAYS = 15
COVERED_CLASSES = {"micro", "small"}


def msmed_deadline(inv: Invoice, supplier: Counterparty | None) -> date | None:
    """Statutory payment deadline, or None when the supplier is out of scope."""
    if supplier is None or (supplier.msme_class or "").lower() not in COVERED_CLASSES:
        return None
    limit = MSMED_WITH_AGREEMENT_DAYS if inv.has_written_agreement else MSMED_NO_AGREEMENT_DAYS
    agreed = min(inv.credit_days, limit)
    return inv.issue_date + timedelta(days=agreed)


@dataclass
class SupplierProfile:
    counterparty_id: str
    name: str
    sector: str | None
    msme_class: str | None
    credit_days: int
    spend_share: float
    lifetime_spend_paise: int
    outstanding_paise: int
    overdue_paise: int
    invoices_open: int
    mean_days_to_pay: float
    early_discount_pct: float
    early_discount_days: int
    discount_opportunity_paise: int
    discount_annualised_return: float | None
    msmed_exposed_paise: int
    msmed_breaches: int
    concentration_flag: bool

    def dict(self) -> dict:
        return asdict(self)


def supplier_profiles(db, business_id: str, as_of: date,
                      lookback_days: int = 540) -> list[SupplierProfile]:
    since = as_of - timedelta(days=lookback_days)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date >= since, Invoice.issue_date <= as_of)).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    by_cp: dict[str, list[Invoice]] = {}
    for i in invs:
        by_cp.setdefault(i.counterparty_id, []).append(i)
    total_spend = sum(i.total_paise for i in invs) or 1

    out: list[SupplierProfile] = []
    for cp_id, rows in by_cp.items():
        cp = parties.get(cp_id)
        if cp is None:
            continue
        spend = sum(i.total_paise for i in rows)
        open_rows = [i for i in rows if i.outstanding_paise > 0]
        outstanding = sum(i.outstanding_paise for i in open_rows)
        overdue = sum(i.outstanding_paise for i in open_rows if i.due_date < as_of)
        paid = [i for i in rows if i.settled_date]
        mean_pay = (sum((i.settled_date - i.issue_date).days for i in paid) / len(paid)) if paid else 0.0

        # Early-payment discount: is it better than our cost of capital?
        disc_amt, ann_return = 0, None
        if cp.early_payment_discount_pct > 0 and open_rows:
            eligible = [i for i in open_rows
                        if as_of <= i.issue_date + timedelta(days=cp.early_payment_days)]
            disc_amt = int(sum(i.outstanding_paise * cp.early_payment_discount_pct for i in eligible))
            days_saved = max(1, cp.credit_days - cp.early_payment_days)
            d = cp.early_payment_discount_pct
            # Effective annualised cost of forgoing the discount.
            ann_return = round((d / (1 - d)) * (365 / days_saved), 4)

        exposed, breaches = 0, 0
        for i in open_rows:
            dl = msmed_deadline(i, cp)
            if dl is None:
                continue
            exposed += i.outstanding_paise
            if dl < as_of:
                breaches += 1

        out.append(SupplierProfile(
            counterparty_id=cp_id, name=cp.name, sector=cp.sector, msme_class=cp.msme_class,
            credit_days=cp.credit_days, spend_share=round(spend / total_spend, 4),
            lifetime_spend_paise=spend, outstanding_paise=outstanding, overdue_paise=overdue,
            invoices_open=len(open_rows), mean_days_to_pay=round(mean_pay, 1),
            early_discount_pct=cp.early_payment_discount_pct,
            early_discount_days=cp.early_payment_days,
            discount_opportunity_paise=disc_amt, discount_annualised_return=ann_return,
            msmed_exposed_paise=exposed, msmed_breaches=breaches,
            concentration_flag=(spend / total_spend) > 0.25))
    out.sort(key=lambda s: -s.outstanding_paise)
    return out


def payment_calendar(db, business_id: str, as_of: date, weeks: int = 13) -> list[dict]:
    """Week-by-week supplier payment obligations, with the statutory deadline
    shown beside the commercial due date where they differ."""
    end = as_of + timedelta(weeks=weeks)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                               InvoiceStatus.WRITTEN_OFF]))).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    weeks_map: dict[date, dict] = {}
    for i in invs:
        if i.outstanding_paise <= 0:
            continue
        cp = parties.get(i.counterparty_id)
        dl = msmed_deadline(i, cp)
        effective = min([d for d in (i.due_date, dl) if d is not None])
        pay_on = max(effective, as_of)
        if pay_on > end:
            continue
        wk = pay_on - timedelta(days=pay_on.weekday())
        e = weeks_map.setdefault(wk, {"week_start": wk.isoformat(), "amount_paise": 0,
                                      "count": 0, "msmed_amount_paise": 0, "items": []})
        e["amount_paise"] += i.outstanding_paise
        e["count"] += 1
        if dl is not None:
            e["msmed_amount_paise"] += i.outstanding_paise
        if len(e["items"]) < 12:
            e["items"].append({
                "invoice_id": i.id, "invoice_no": i.invoice_no,
                "supplier": cp.name if cp else "Unknown",
                "amount_paise": i.outstanding_paise,
                "due_date": i.due_date.isoformat(),
                "statutory_deadline": dl.isoformat() if dl else None,
                "msme_class": cp.msme_class if cp else None,
                "overdue": i.due_date < as_of})
    return [weeks_map[k] for k in sorted(weeks_map)]


def msmed_exposure(db, business_id: str, as_of: date) -> dict:
    """Total purchase value at risk of a 43B(h) disallowance."""
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                               InvoiceStatus.WRITTEN_OFF]))).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    breached, at_risk_14d, covered_total, items = 0, 0, 0, []
    for i in invs:
        cp = parties.get(i.counterparty_id)
        dl = msmed_deadline(i, cp)
        if dl is None or i.outstanding_paise <= 0:
            continue
        covered_total += i.outstanding_paise
        days = (dl - as_of).days
        if days < 0:
            breached += i.outstanding_paise
        elif days <= 14:
            at_risk_14d += i.outstanding_paise
        if days <= 14:
            items.append({"invoice_id": i.id, "invoice_no": i.invoice_no,
                          "supplier": cp.name, "msme_class": cp.msme_class,
                          "amount_paise": i.outstanding_paise,
                          "statutory_deadline": dl.isoformat(), "days_remaining": days})
    items.sort(key=lambda x: x["days_remaining"])
    return {
        "as_of": as_of.isoformat(),
        "covered_outstanding_paise": covered_total,
        "already_breached_paise": breached,
        "due_within_14_days_paise": at_risk_14d,
        "items": items[:40],
        "rule": ("MSMED Act s.15 read with Income-tax s.43B(h): payment to a registered "
                 "micro or small enterprise within 45 days where a written agreement "
                 "exists, otherwise 15 days. Medium enterprises are outside the rule."),
        "caveat": ("Based on the MSME class recorded against each supplier. Confirm each "
                   "supplier's Udyam registration before relying on this for a tax filing."),
    }
