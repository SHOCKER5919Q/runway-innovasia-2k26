"""Manual entry: typing a transaction or invoice straight into RUNWAY.

Most MSME ledgers are only partly digital. A cash payment made at the counter,
a post-dated cheque, a bill raised on paper - none of those reach a bank feed,
and a forecast built only on imported rows quietly assumes they do not exist.
Manual entry closes that hole.

The point of routing typed input through the *same* pipeline as an import -
fingerprint, duplicate check, counterparty resolution, classification,
reconciliation - is that a hand-entered row ends up with the same provenance
and the same quality signals as one that arrived in a file. Nothing here
trusts the operator's category over the evidence, and nothing here is marked
``verified_actual`` just because a human typed it.

Manual rows are tagged ``source_system = 'manual'`` so they can always be
told apart from imported ones, and only they can be deleted again.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit
from app.core.enums import (
    Direction, Evidence, InvoiceKind, InvoiceStatus, PartyType, ReconStatus, Role,
    TxnCategory,
)
from app.core.money import rupees_to_paise
from app.digital_twin.digital_twin_service import invalidate
from app.ledger.classifier import classify
from app.ledger.entities import resolve_counterparty
from app.ledger.normalise import (
    detect_duplicate, fingerprint, mark_suspected_duplicate, party_key,
)
from app.ledger.reconciliation import (
    apply_match, match_transaction, reconcile_invoice_against_unallocated,
    refresh_overdue,
)
from app.models import Account, Counterparty, Invoice, Transaction, _uid

router = APIRouter(prefix="/api", tags=["entry"])
AsOf = Annotated[date, Depends(today_param)]

MANUAL_SOURCE = "manual"


def _default_account(db, business_id: str) -> Account:
    """The account a typed row lands in when the operator does not pick one.

    Preference order matters: an operating current account before an OD
    account, because a manual entry is almost always "cash moved through the
    main bank", and guessing the overdraft would misstate available liquidity.
    """
    rows = db.scalars(select(Account).where(
        Account.business_id == business_id, Account.is_active.is_(True))).all()
    if not rows:
        raise HTTPException(400, "This workspace has no bank account to post to")
    for kind in ("current", "savings", "cash"):
        for a in rows:
            if a.kind == kind:
                return a
    return rows[0]


def ensure_counterparty(db, business_id: str, *, name: str | None,
                        party_type: str | None = None,
                        counterparty_id: str | None = None,
                        gstin: str | None = None, phone: str | None = None,
                        email: str | None = None,
                        credit_days: int | None = None) -> tuple[Counterparty | None, str]:
    """Find or create the party this row belongs to.

    Returns ``(counterparty, note)`` so the response can say whether it
    matched an existing party or had to create one - an owner should be able
    to see that "Ravi Kumar" was silently linked to an existing supplier.
    """
    if counterparty_id:
        cp = db.get(Counterparty, counterparty_id)
        if not cp or cp.business_id != business_id:
            raise HTTPException(404, "Counterparty not found")
        return cp, "linked to the selected counterparty"
    if not name or not name.strip():
        return None, "no counterparty given"

    name = name.strip()
    key = party_key(name)
    cp = db.scalar(select(Counterparty).where(
        Counterparty.business_id == business_id,
        Counterparty.normalised_name == key))
    if cp:
        return cp, f"matched existing counterparty '{cp.name}'"
    if not party_type:
        party_type = PartyType.CUSTOMER
    cp = Counterparty(
        id=_uid(), business_id=business_id, name=name, normalised_name=key,
        party_type=party_type, gstin=gstin, contact_phone=phone,
        contact_email=email, credit_days=int(credit_days or 30),
        aliases_json=[], notes="Created from manual entry.")
    db.add(cp)
    db.flush()
    return cp, f"created new counterparty '{cp.name}'"


# ─────────────────────────── counterparties ────────────────────────────

class CounterpartyIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    party_type: str = PartyType.CUSTOMER
    gstin: str | None = Field(default=None, max_length=15)
    credit_days: int = Field(default=30, ge=0, le=365)
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=20)
    contact_email: str | None = Field(default=None, max_length=160)


@router.post("/counterparties", status_code=201)
def create_counterparty(body: CounterpartyIn, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    if body.party_type not in list(PartyType):
        raise HTTPException(400, f"unknown party type '{body.party_type}'")
    cp, note = ensure_counterparty(
        db, ctx.business_id, name=body.name, party_type=body.party_type,
        gstin=body.gstin, phone=body.contact_phone, email=body.contact_email,
        credit_days=body.credit_days)
    if cp is None:
        raise HTTPException(400, "a name is required")
    if note.startswith("matched"):
        raise HTTPException(409, f"'{cp.name}' already exists in this workspace")
    if body.contact_name:
        cp.contact_name = body.contact_name
    audit(db, ctx, "counterparty.create", entity="counterparty", entity_id=cp.id,
          detail={"name": cp.name, "party_type": cp.party_type})
    db.commit()
    return jsonable({"id": cp.id, "name": cp.name, "party_type": cp.party_type,
                     "note": note})


# ──────────────────────────── transactions ─────────────────────────────

class TxnIn(BaseModel):
    value_date: date
    direction: str
    amount_rupees: float = Field(gt=0)
    narration: str = Field(min_length=1, max_length=400)
    reference_no: str | None = Field(default=None, max_length=80)
    counterparty_id: str | None = None
    counterparty_name: str | None = Field(default=None, max_length=200)
    account_id: str | None = None
    category: str | None = None
    # Gateway settlements: the customer paid the gross, the bank got the net.
    gross_rupees: float | None = Field(default=None, gt=0)
    fee_rupees: float | None = Field(default=None, ge=0)
    posting_date: date | None = None
    auto_reconcile: bool = True


@router.post("/transactions", status_code=201)
def create_transaction(body: TxnIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Record a payment or receipt by hand, through the full import pipeline."""
    ctx.require(Role.MANAGER)
    if body.direction not in (Direction.CREDIT, Direction.DEBIT):
        raise HTTPException(400, "direction must be 'credit' or 'debit'")
    if body.value_date > as_of:
        raise HTTPException(
            400, "A manual entry cannot be dated in the future - the cash has "
                 "either moved or it has not.")

    account = (db.get(Account, body.account_id) if body.account_id else None) \
        or _default_account(db, ctx.business_id)
    if account.business_id != ctx.business_id:
        raise HTTPException(404, "Account not found")

    amount = rupees_to_paise(body.amount_rupees)
    if amount <= 0:
        raise HTTPException(400, "amount must be greater than zero")

    gross = rupees_to_paise(body.gross_rupees) if body.gross_rupees else None
    fee = rupees_to_paise(body.fee_rupees) if body.fee_rupees else 0
    if gross is not None and gross < amount:
        raise HTTPException(400, "gross cannot be less than the amount received")
    if gross is None and fee:
        gross = amount + fee

    party_note = "no counterparty"
    cp = None
    if body.counterparty_id or body.counterparty_name:
        expected = PartyType.CUSTOMER if body.direction == Direction.CREDIT \
            else PartyType.SUPPLIER
        cp, party_note = ensure_counterparty(
            db, ctx.business_id, name=body.counterparty_name,
            counterparty_id=body.counterparty_id, party_type=expected)

    txn = Transaction(
        id=_uid(), business_id=ctx.business_id, account_id=account.id,
        source_system=MANUAL_SOURCE, source_ref=body.reference_no,
        value_date=body.value_date, posting_date=body.posting_date or body.value_date,
        amount_paise=amount, direction=body.direction, narration=body.narration,
        reference_no=body.reference_no,
        # A typed row is an owner statement, not a reconciled bank record. It
        # sits below imported-actual in the evidence hierarchy until it is
        # matched against something external.
        evidence=Evidence.OWNER_ESTIMATE,
        recon_status=ReconStatus.UNRECONCILED, allocated_paise=0,
        gross_paise=gross, fee_paise=fee,
        counterparty_id=cp.id if cp else None,
        raw_json={"entered_by": ctx.user.id, "narration": body.narration},
        transform_log_json=[{"step": "manual_entry", "by": ctx.user.id,
                             "value_date": body.value_date.isoformat()}])
    txn.fingerprint = fingerprint(
        business_id=ctx.business_id, account_id=account.id,
        value_date=txn.value_date, amount_paise=amount, direction=body.direction,
        reference_no=body.reference_no, narration=body.narration)

    dup_note = "no duplicate found"
    is_dup, existing_id, reason = detect_duplicate(db, ctx.business_id, txn)
    if is_dup:
        raise HTTPException(
            409, {"detail": "This looks like a row you already have.",
                  "reason": reason, "existing_transaction_id": existing_id})
    if existing_id:
        mark_suspected_duplicate(txn, existing_id, reason)
        dup_note = f"flagged as a possible duplicate of {existing_id}: {reason}"

    # Narration-only resolution is unreliable for a hand-typed row, so an
    # explicit pick always wins and we only guess when nothing was given.
    if cp is None and not body.counterparty_id:
        cid, conf, why = resolve_counterparty(db, ctx.business_id, body.narration,
                                              body.direction)
        txn.counterparty_id = cid
        party_note = why
        if cid:
            party_note = f"{why} (guessed from the narration)"

    cp_type = None
    if txn.counterparty_id:
        p = db.get(Counterparty, txn.counterparty_id)
        cp_type = p.party_type if p else None

    if body.category:
        if body.category not in list(TxnCategory):
            raise HTTPException(400, f"unknown category '{body.category}'")
        cat, conf, rule = body.category, 0.85, "chosen by the operator"
    else:
        cat, conf, rule = classify(body.narration, body.direction,
                                   counterparty_type=cp_type)
    txn.category, txn.category_confidence, txn.category_source = cat, conf, rule
    txn.transform_log_json = list(txn.transform_log_json) + [
        {"step": "resolve_counterparty", "note": party_note},
        {"step": "classify", "category": cat, "confidence": conf, "rule": rule},
        {"step": "duplicate_check", "note": dup_note}]

    db.add(txn)
    db.flush()

    recon = {"status": txn.recon_status, "allocations": 0,
             "amount_allocated_paise": 0, "note": "reconciliation skipped"}
    if body.auto_reconcile:
        res = match_transaction(db, txn)
        allocs = apply_match(db, txn, res)
        recon = {"status": txn.recon_status, "allocations": len(allocs),
                 "amount_allocated_paise": sum(a.amount_paise for a in allocs),
                 "note": res.note or ("matched to open invoices" if allocs
                                      else "no open invoice matched this payment")}
        # A typed row that has been matched against a real invoice on file is
        # no longer a bare assertion - that is exactly what promotion means.
        if allocs:
            txn.evidence = Evidence.VERIFIED_ACTUAL

    refresh_overdue(db, ctx.business_id, as_of)
    audit(db, ctx, "transaction.create", entity="transaction", entity_id=txn.id,
          detail={"amount_paise": amount, "direction": body.direction,
                  "category": cat, "recon_status": txn.recon_status})
    db.commit()
    invalidate(ctx.business_id)

    return jsonable({
        "id": txn.id, "date": txn.value_date.isoformat(),
        "narration": txn.narration, "direction": txn.direction,
        "amount": money(txn.amount_paise),
        "gross": money(txn.gross_paise) if txn.gross_paise else None,
        "fee": money(txn.fee_paise) if txn.fee_paise else None,
        "category": txn.category, "category_confidence": txn.category_confidence,
        "category_rule": txn.category_source,
        "counterparty": {"id": cp.id, "name": cp.name} if cp else None,
        "evidence": txn.evidence, "recon_status": txn.recon_status,
        "duplicate_of": txn.duplicate_of,
        "allocated": money(txn.allocated_paise),
        "unallocated": money(txn.unallocated_paise),
        "source_system": txn.source_system,
        "pipeline": {"counterparty": party_note, "duplicate": dup_note,
                     "classification": rule, "reconciliation": recon},
    })


@router.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: str, db: DbDep, ctx: Tenant):
    """Remove a hand-entered row, undoing whatever it settled.

    Only rows created here can be deleted. An imported row is somebody else's
    record of what happened; the way to correct it is to categorise or flag
    it, not to make it disappear.
    """
    ctx.require(Role.MANAGER)
    t = db.get(Transaction, txn_id)
    if not t or t.business_id != ctx.business_id:
        raise HTTPException(404, "Transaction not found")
    if t.source_system != MANUAL_SOURCE:
        raise HTTPException(
            409, "Only rows entered by hand can be deleted. Imported rows are "
                 "corrected by re-categorising or flagging them, never removed.")

    # Undo the settlements this row created, or the invoices it paid would
    # stay paid after the payment has gone.
    released = []
    from app.models import Allocation
    allocs = db.scalars(select(Allocation).where(
        Allocation.transaction_id == t.id)).all()
    for a in allocs:
        inv = db.get(Invoice, a.invoice_id)
        if inv is None:
            continue
        inv.settled_paise = max(0, inv.settled_paise - a.amount_paise)
        if inv.settled_paise <= 0:
            inv.first_payment_date = None
            inv.settled_date = None
        inv.status = (InvoiceStatus.PAID if inv.outstanding_paise <= 0
                      else InvoiceStatus.PART_PAID if inv.settled_paise > 0
                      else InvoiceStatus.OPEN)
        released.append({"invoice_id": inv.id, "invoice_no": inv.invoice_no,
                         "amount": money(a.amount_paise)})
        db.delete(a)

    audit(db, ctx, "transaction.delete", entity="transaction", entity_id=t.id,
          detail={"amount_paise": t.amount_paise, "released": released})
    db.delete(t)
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"deleted": t.id, "released_allocations": released})


# ───────────────────────────── invoices ────────────────────────────────

class InvoiceIn(BaseModel):
    kind: str = InvoiceKind.SALES
    invoice_no: str = Field(min_length=1, max_length=60)
    counterparty_id: str | None = None
    counterparty_name: str | None = Field(default=None, max_length=200)
    issue_date: date
    due_date: date | None = None
    credit_days: int | None = Field(default=None, ge=0, le=365)
    amount_rupees: float = Field(gt=0)
    gst_rate: float = Field(default=0.18, ge=0, le=0.5)
    taxable_rupees: float | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=500)


@router.post("/invoices", status_code=201)
def create_invoice(body: InvoiceIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Raise a bill or record a purchase invoice by hand."""
    ctx.require(Role.MANAGER)
    if body.kind not in (InvoiceKind.SALES, InvoiceKind.PURCHASE):
        raise HTTPException(400, "kind must be 'sales' or 'purchase'")

    total = rupees_to_paise(body.amount_rupees)
    if total <= 0:
        raise HTTPException(400, "amount must be greater than zero")
    taxable = (rupees_to_paise(body.taxable_rupees) if body.taxable_rupees
               else int(round(total / (1.0 + body.gst_rate))))
    if taxable > total:
        raise HTTPException(400, "taxable value cannot exceed the invoice total")

    cp, party_note = ensure_counterparty(
        db, ctx.business_id, name=body.counterparty_name,
        counterparty_id=body.counterparty_id,
        party_type=(PartyType.CUSTOMER if body.kind == InvoiceKind.SALES
                    else PartyType.SUPPLIER))
    if cp is None:
        raise HTTPException(400, "an invoice needs a customer or supplier")

    credit_days = body.credit_days if body.credit_days is not None else (
        cp.credit_days or 30)
    due = body.due_date or (body.issue_date + timedelta(days=int(credit_days)))
    if due < body.issue_date:
        raise HTTPException(400, "due date cannot be before the issue date")

    exists = db.scalar(select(Invoice).where(
        Invoice.business_id == ctx.business_id, Invoice.kind == body.kind,
        Invoice.invoice_no == body.invoice_no))
    if exists:
        raise HTTPException(409, f"'{body.invoice_no}' already exists in this workspace")

    inv = Invoice(
        id=_uid(), business_id=ctx.business_id, counterparty_id=cp.id,
        kind=body.kind, invoice_no=body.invoice_no, issue_date=body.issue_date,
        due_date=due, credit_days=int(credit_days),
        taxable_paise=taxable, tax_paise=total - taxable, total_paise=total,
        settled_paise=0, written_off_paise=0,
        status=InvoiceStatus.OVERDUE if due < as_of else InvoiceStatus.OPEN,
        gst_rate=body.gst_rate, source_system=MANUAL_SOURCE,
        evidence=Evidence.OWNER_ESTIMATE, notes=body.notes,
        raw_json={"entered_by": ctx.user.id})
    db.add(inv)
    db.flush()

    # A bill raised today can be settled by a payment that is already on the
    # books - the owner often enters the invoice after the money arrived.
    matched = reconcile_invoice_against_unallocated(db, inv)

    refresh_overdue(db, ctx.business_id, as_of)
    audit(db, ctx, "invoice.create", entity="invoice", entity_id=inv.id,
          detail={"invoice_no": inv.invoice_no, "kind": inv.kind,
                  "total_paise": total, "due_date": due.isoformat()})
    db.commit()
    invalidate(ctx.business_id)

    return jsonable({
        "id": inv.id, "invoice_no": inv.invoice_no, "kind": inv.kind,
        "counterparty": {"id": cp.id, "name": cp.name},
        "issue_date": inv.issue_date.isoformat(), "due_date": inv.due_date.isoformat(),
        "credit_days": inv.credit_days,
        "days_past_due": (as_of - inv.due_date).days,
        "total": money(inv.total_paise), "taxable": money(inv.taxable_paise),
        "tax": money(inv.tax_paise), "settled": money(inv.settled_paise),
        "outstanding": money(inv.outstanding_paise), "status": inv.status,
        "evidence": inv.evidence, "gst_rate": inv.gst_rate,
        "pipeline": {"counterparty": party_note,
                     "auto_matched_payments": matched},
    })


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, db: DbDep, ctx: Tenant):
    """Withdraw a hand-entered invoice and release any payment it absorbed."""
    ctx.require(Role.MANAGER)
    inv = db.get(Invoice, invoice_id)
    if not inv or inv.business_id != ctx.business_id:
        raise HTTPException(404, "Invoice not found")
    if inv.source_system != MANUAL_SOURCE:
        raise HTTPException(
            409, "Only invoices entered by hand can be deleted. Imported "
                 "invoices are corrected, never removed.")
    from app.models import Allocation
    released = []
    for a in db.scalars(select(Allocation).where(
            Allocation.invoice_id == inv.id)).all():
        txn = db.get(Transaction, a.transaction_id)
        if txn is not None:
            txn.allocated_paise = max(0, txn.allocated_paise - a.amount_paise)
            if txn.allocated_paise <= 0 and \
                    txn.recon_status in (ReconStatus.MATCHED, ReconStatus.PARTIALLY_MATCHED):
                txn.recon_status = ReconStatus.UNRECONCILED
        released.append({"transaction_id": a.transaction_id,
                         "amount": money(a.amount_paise)})
        db.delete(a)
    audit(db, ctx, "invoice.delete", entity="invoice", entity_id=inv.id,
          detail={"invoice_no": inv.invoice_no, "released_payments": len(released)})
    db.delete(inv)
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"deleted": inv.id, "invoice_no": inv.invoice_no,
                     "released_payments": released})
