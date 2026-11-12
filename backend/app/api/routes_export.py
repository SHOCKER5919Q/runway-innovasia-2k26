"""Exports and shareable briefings.

Two things an owner actually needs to *do* with what RUNWAY computed:

1. Hand it to somebody else - the accountant, the bank, a partner. That means
   a CSV, not a screenshot: the numbers have to stay numeric, in paise, with
   the state they came from written next to them.
2. Act on it today. That means a message, not a dashboard: a WhatsApp note to
   the owner in the morning, and a payment reminder they can forward to a
   customer who is late.

Neither of these is a new model. They are renderings of numbers the engine
already produced, which is the only kind of feature that cannot drift out of
sync with the forecast.
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit
from app.api.routes_reports import _passport
from app.core.enums import InvoiceKind, InvoiceStatus, Role
from app.core.money import format_inr, paise_to_rupees
from app.digital_twin.digital_twin_service import get_bundle
from app.models import Counterparty, Invoice, Transaction

router = APIRouter(prefix="/api", tags=["export"])
AsOf = Annotated[date, Depends(today_param)]


def _csv(filename: str, header: list[str], rows: list[list]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),   # BOM: Excel opens ₹ correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in (name or "business").strip()).strip("-").lower()


# ─────────────────────────── CSV exports ───────────────────────────────

@router.get("/exports/transactions.csv")
def export_transactions(db: DbDep, ctx: Tenant,
                        date_from: str | None = None, date_to: str | None = None,
                        category: str | None = None, direction: str | None = None,
                        needs_review: bool = False, q: str | None = None):
    stmt = select(Transaction).where(Transaction.business_id == ctx.business_id)
    if date_from:
        stmt = stmt.where(Transaction.value_date >= date.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Transaction.value_date <= date.fromisoformat(date_to))
    if category:
        stmt = stmt.where(Transaction.category == category)
    if direction:
        stmt = stmt.where(Transaction.direction == direction)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Transaction.narration.ilike(like))
    rows = db.scalars(stmt.order_by(Transaction.value_date.desc())).all()
    names = {c.id: c.name for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == ctx.business_id)).all()}
    if needs_review:
        rows = [t for t in rows if t.recon_status in ("needs_review", "duplicate_suspect")
                or t.category_confidence < 0.55]

    return _csv(
        f"runway-transactions-{date.today().isoformat()}.csv",
        ["date", "narration", "reference", "direction", "amount_paise",
         "amount_rupees", "category", "category_confidence", "category_rule",
         "counterparty", "account_id", "recon_status", "evidence",
         "allocated_paise", "unallocated_paise", "duplicate_of", "source_system"],
        [[t.value_date.isoformat(), t.narration, t.reference_no or "", t.direction,
          t.amount_paise, paise_to_rupees(t.amount_paise), t.category,
          round(t.category_confidence, 3), t.category_source,
          names.get(t.counterparty_id) or "", t.account_id, t.recon_status,
          t.evidence, t.allocated_paise, t.unallocated_paise, t.duplicate_of or "",
          t.source_system] for t in rows])


@router.get("/exports/receivables.csv")
def export_receivables(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return _csv(
        f"runway-receivables-{as_of.isoformat()}.csv",
        ["invoice_no", "customer", "issue_date", "due_date", "days_past_due",
         "outstanding_paise", "outstanding_rupees", "total_paise",
         "risk_band", "reliability_score", "predicted_pay_date",
         "predicted_delay_days", "prob_within_15", "priority_score",
         "recommended_action", "predicted_state"],
        [[c["invoice_no"], c["customer"], c["issue_date"], c["due_date"],
          c["days_past_due"], c["outstanding_paise"],
          paise_to_rupees(c["outstanding_paise"]), c["total_paise"],
          c["risk_band"], c["reliability_score"], c["predicted_pay_date"],
          c["predicted_delay_days"], c["prob_within_15"], c["priority_score"],
          c["recommended_action"], "predicted"] for c in b.collection_list])


@router.get("/exports/payables.csv")
def export_payables(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    rows = []
    for week in b.payment_calendar:
        for it in week["items"]:
            rows.append([week["week_start"], it["invoice_no"], it["supplier"],
                         it["due_date"], it["statutory_deadline"] or "",
                         it["amount_paise"], paise_to_rupees(it["amount_paise"]),
                         it["msme_class"] or "", "yes" if it["overdue"] else "no"])
    return _csv(
        f"runway-payables-{as_of.isoformat()}.csv",
        ["week_start", "invoice_no", "supplier", "due_date", "statutory_deadline",
         "amount_paise", "amount_rupees", "msme_class", "overdue"],
        rows)


@router.get("/exports/passport.csv")
def export_passport(db: DbDep, ctx: Tenant, as_of: AsOf):
    """The Cash Health Passport as a flat, lender-readable table.

    Each row is one disclosed figure with the basis it was computed on and the
    evidence rank it holds. Flattening it this way is deliberate: it is the
    form a credit analyst can paste into their own model, and it keeps every
    number next to its own caveat.
    """
    p = _passport(db, ctx.business_id, as_of)
    rows = []
    for s in p["sections"]:
        value = s["value"]
        items = value if isinstance(value, list) else [value]
        for it in items:
            if isinstance(it, dict):
                for k, v in it.items():
                    if isinstance(v, dict):
                        v = v.get("paise", v.get("display", v))
                    rows.append([s["key"], s["label"], k, v, s["basis"], s["verification"]])
            else:
                rows.append([s["key"], s["label"], "", it, s["basis"], s["verification"]])
    header = ["section_key", "section", "field", "value", "basis", "evidence"]
    rows = [r for r in rows] + [
        ["meta", "Report", "business", p["business"]["name"], "as supplied", "actual"],
        ["meta", "Report", "as_of", p["as_of"], "reporting date", "actual"],
        ["meta", "Report", "generated_at", p["generated_at"], "system clock", "actual"],
        ["meta", "Report", "ledger_fingerprint", p["state_refs"]["ledger_fingerprint"],
         "hash of the ledger this report was computed from", "actual"],
    ]
    return _csv(f"runway-passport-{_slug(p['business']['name'])}-{as_of.isoformat()}.csv",
                header, rows)


# ──────────────────────────── briefings ────────────────────────────────

def _briefing_lines(b, as_of: date, name: str) -> list[str]:
    s, a = b.simulation, b.actual_snapshot
    out = [f"*{name} — {as_of:%d %b %Y}*", ""]

    out.append(f"Cash available: {format_inr(a.available_liquidity_paise)}")
    out.append(f"  Bank balance {format_inr(a.cash_paise)}, less "
               f"{format_inr(a.restricted_paise)} lien-marked and "
               f"{format_inr(a.committed_paise)} already committed.")
    out.append("")

    if s:
        wk4 = min(4, len(s.p50) - 1)
        out.append(f"In 30 days (predicted): {format_inr(s.p50[wk4])}")
        out.append(f"  Downside (P10) {format_inr(s.p10[wk4])}, "
                   f"upside (P90) {format_inr(s.p90[wk4])}.")
        out.append(f"  {s.breach_probability:.0%} of {s.paths:,} simulated paths fall "
                   f"below your {format_inr(s.safety_buffer_paise)} buffer.")
        out.append("")

    overdue = [c for c in b.collection_list if c["days_past_due"] > 0]
    if overdue:
        total = sum(c["outstanding_paise"] for c in overdue)
        out.append(f"Overdue receivables: {format_inr(total)} across {len(overdue)} invoices")
        for c in overdue[:3]:
            out.append(f"  • {c['customer']} — {format_inr(c['outstanding_paise'])}, "
                       f"{c['days_past_due']}d late")
        out.append("")

    due_soon = [o for o in b.obligations["items"] if 0 <= o["days_away"] <= 10]
    if due_soon:
        out.append("Due in the next 10 days:")
        for o in sorted(due_soon, key=lambda x: x["days_away"])[:4]:
            out.append(f"  • {o['label']} — {format_inr(o['amount_paise'])} in "
                       f"{o['days_away']}d")
        out.append("")

    if b.recommendations:
        r = b.recommendations[0]
        out.append(f"Today's move: {r.title}")
        out.append(f"  {r.required_action}")
        if r.expected_effect_text:
            out.append(f"  Expected effect: {r.expected_effect_text}")
        out.append("")

    out.append(f"Health {b.health['score']}/100 ({b.health['band']}). "
               f"Predictions are model estimates, not recorded facts.")
    return out


@router.get("/briefing/whatsapp")
def briefing_whatsapp(db: DbDep, ctx: Tenant, as_of: AsOf):
    """The morning briefing as a message the owner can send or keep.

    Plain text with no markup beyond bold asterisks, sized to fit one phone
    screen. Everything predicted is labelled as such in the message itself -
    a forwarded note is read by people who have never seen the app.
    """
    b = get_bundle(db, ctx.business_id, as_of)
    lines = _briefing_lines(b, as_of, b.business.name)
    text = "\n".join(lines)
    return jsonable({
        "as_of": as_of.isoformat(),
        "channel": "whatsapp",
        "text": text,
        "char_count": len(text),
        "business": b.business.name,
        "share_url": "https://wa.me/?text=" + _urlquote(text),
        "disclaimer": ("Predicted figures are model estimates with stated "
                       "uncertainty, not recorded facts."),
    })


@router.get("/briefing/email")
def briefing_email(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of)
    body = "\n".join(_briefing_lines(b, as_of, b.business.name))
    subject = (f"{b.business.name} — cash briefing {as_of:%d %b %Y} "
               f"(health {b.health['score']}/100)")
    return jsonable({
        "as_of": as_of.isoformat(),
        "channel": "email",
        "subject": subject,
        "text": body,
        "mailto_url": "mailto:?subject=" + _urlquote(subject) +
                      "&body=" + _urlquote(body),
        "char_count": len(body),
    })


def _urlquote(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


# ───────────────────── collection reminders ────────────────────────────

@router.get("/receivables/{invoice_id}/reminder")
def collection_reminder(invoice_id: str, db: DbDep, ctx: Tenant, as_of: AsOf,
                        tone: str = Query("firm", pattern="^(polite|firm|final)$"),
                        channel: str = Query("whatsapp", pattern="^(whatsapp|email|sms)$")):
    """A ready-to-send payment reminder for one overdue invoice.

    The wording is a template, but every number in it is the customer's own
    ledger position - amount, invoice, days late - so the owner is not asked
    to retype anything and cannot send the wrong figure by accident.

    Three tones, because chasing a 12-day delay and a 90-day delay are not the
    same conversation. RUNWAY never sends this itself and never contacts a
    customer; it composes the message and the owner decides.
    """
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.business_id != ctx.business_id or inv.kind != InvoiceKind.SALES:
        raise HTTPException(404, "Sales invoice not found")
    cp = db.get(Counterparty, inv.counterparty_id)
    outstanding = max(0, inv.total_paise - inv.settled_paise - inv.written_off_paise)
    days = (as_of - inv.due_date).days

    biz = ctx.business
    amount = format_inr(outstanding)
    first = (cp.name.split()[0] if cp and cp.name else "there")

    if tone == "polite":
        body = (f"Hi {first}, a quick note that invoice {inv.invoice_no} for "
                f"{amount} was due on {inv.due_date:%d %b %Y}. "
                f"If it is already in process, please ignore this. "
                f"Otherwise could you confirm a payment date?")
    elif tone == "final":
        body = (f"Hi {first}, invoice {inv.invoice_no} for {amount} is now "
                f"{max(0, days)} days past its due date of {inv.due_date:%d %b %Y}. "
                f"We need this cleared this week. Please confirm by when we can "
                f"expect it, or let us know if there is a dispute we should resolve.")
    else:
        body = (f"Hi {first}, following up on invoice {inv.invoice_no} for "
                f"{amount}, due {inv.due_date:%d %b %Y}"
                + (f" and now {days} days overdue" if days > 0 else "") +
                ". Could you confirm the payment date today?")

    body += f"\n\n— {biz.name}"
    if cp and cp.contact_name:
        pass

    subject = f"Payment reminder: invoice {inv.invoice_no} — {amount}"
    phone = (cp.contact_phone if cp else None) or ""
    digits = "".join(ch for ch in phone if ch.isdigit())[-10:]

    audit(db, ctx, "reminder.compose", entity="invoice", entity_id=inv.id,
          detail={"tone": tone, "channel": channel, "days_past_due": days})
    db.commit()

    return jsonable({
        "invoice_id": inv.id, "invoice_no": inv.invoice_no,
        "customer": {"id": cp.id if cp else None, "name": cp.name if cp else None,
                     "phone": phone or None},
        "as_of": as_of.isoformat(),
        "days_past_due": days, "tone": tone, "channel": channel,
        "outstanding": money(outstanding), "total": money(inv.total_paise),
        "settled": money(inv.settled_paise), "due_date": inv.due_date.isoformat(),
        "subject": subject if channel == "email" else None,
        "text": body,
        "share_url": ("https://wa.me/" + (f"{digits}" if digits else "") + "?text="
                      + _urlquote(body)) if channel == "whatsapp"
                     else (("sms:" + digits + "?&body=" + _urlquote(body))
                           if channel == "sms" and digits
                           else ("mailto:?subject=" + _urlquote(subject) +
                                 "&body=" + _urlquote(body))),
        "note": ("RUNWAY composes this message; it does not send it and never "
                 "contacts your customer. Check the wording before you forward it."),
    })


@router.get("/receivables/reminders.csv")
def reminders_csv(db: DbDep, ctx: Tenant, as_of: AsOf,
                  tone: str = Query("firm", pattern="^(polite|firm|final)$"),
                  min_days_past_due: int = Query(1, ge=0)):
    """Every overdue invoice as one sheet of ready-to-send reminders."""
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    rows = []
    for c in b.collection_list:
        if c["days_past_due"] < min_days_past_due:
            continue
        inv = db.get(Invoice, c["invoice_id"])
        cp = db.get(Counterparty, c["counterparty_id"]) if c["counterparty_id"] else None
        r = collection_reminder(inv.id, db, ctx, as_of, tone=tone, channel="whatsapp")
        rows.append([c["invoice_no"], c["customer"],
                     (cp.contact_phone if cp else "") or "",
                     c["days_past_due"], c["outstanding_paise"],
                     paise_to_rupees(c["outstanding_paise"]), tone,
                     r["text"].replace("\r", " ").replace("\n", " ")])
    return _csv(
        f"runway-reminders-{as_of.isoformat()}.csv",
        ["invoice_no", "customer", "phone", "days_past_due", "outstanding_paise",
         "outstanding_rupees", "tone", "message"],
        rows)
