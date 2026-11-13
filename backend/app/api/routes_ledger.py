"""Ledger surface: transactions, invoices, counterparties, compliance."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit, resolved_as_of
from app.core.enums import (
    AccountKind, Direction, Evidence, InvoiceKind, InvoiceStatus,
    ObligationKind, ReconStatus, Role,
)
from app.digital_twin.digital_twin_service import get_bundle, invalidate
from app.models import (
    Account, Allocation, Counterparty, Invoice, Loan, Obligation,
    Transaction, _uid,
)

router = APIRouter(prefix="/api", tags=["ledger"])
AsOf = Annotated[date, Depends(resolved_as_of)]


@router.get("/transactions")
def list_transactions(
    db: DbDep, ctx: Tenant,
    q: str | None = Query(None, description="free text over narration and reference"),
    category: str | None = None, direction: str | None = None,
    recon_status: str | None = None, counterparty_id: str | None = None,
    account_id: str | None = None,
    import_batch_id: str | None = Query(None, description="rows added by one upload"),
    date_from: str | None = None, date_to: str | None = None,
    min_paise: int | None = None, max_paise: int | None = None,
    needs_review: bool = False,
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|amount_desc|amount_asc)$"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(Transaction).where(Transaction.business_id == ctx.business_id)
    if import_batch_id:
        stmt = stmt.where(Transaction.import_batch_id == import_batch_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Transaction.narration.ilike(like),
                              Transaction.reference_no.ilike(like)))
    if category:
        stmt = stmt.where(Transaction.category == category)
    if direction:
        stmt = stmt.where(Transaction.direction == direction)
    if recon_status:
        stmt = stmt.where(Transaction.recon_status == recon_status)
    if counterparty_id:
        stmt = stmt.where(Transaction.counterparty_id == counterparty_id)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if date_from:
        stmt = stmt.where(Transaction.value_date >= date.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(Transaction.value_date <= date.fromisoformat(date_to))
    if min_paise is not None:
        stmt = stmt.where(Transaction.amount_paise >= min_paise)
    if max_paise is not None:
        stmt = stmt.where(Transaction.amount_paise <= max_paise)
    if needs_review:
        stmt = stmt.where(or_(
            Transaction.recon_status.in_([ReconStatus.NEEDS_REVIEW,
                                          ReconStatus.DUPLICATE_SUSPECT]),
            Transaction.category_confidence < 0.55))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {"date_desc": Transaction.value_date.desc(),
             "date_asc": Transaction.value_date.asc(),
             "amount_desc": Transaction.amount_paise.desc(),
             "amount_asc": Transaction.amount_paise.asc()}[sort]
    rows = db.scalars(stmt.order_by(order, Transaction.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    names = {c.id: c.name for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == ctx.business_id)).all()}
    return jsonable({
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": [{
            "id": t.id, "date": t.value_date.isoformat(),
            "posting_date": t.posting_date.isoformat() if t.posting_date else None,
            "narration": t.narration, "reference_no": t.reference_no,
            "direction": t.direction, "amount": money(t.amount_paise),
            "signed": money(t.signed_paise),
            "gross": money(t.gross_paise) if t.gross_paise else None,
            "fee": money(t.fee_paise) if t.fee_paise else None,
            "category": t.category, "category_confidence": t.category_confidence,
            "category_rule": t.category_source,
            "counterparty_id": t.counterparty_id,
            "counterparty": names.get(t.counterparty_id),
            "account_id": t.account_id, "evidence": t.evidence,
            "recon_status": t.recon_status, "allocated": money(t.allocated_paise),
            "unallocated": money(t.unallocated_paise),
            "duplicate_of": t.duplicate_of, "source_system": t.source_system,
            "needs_review": (t.recon_status in (ReconStatus.NEEDS_REVIEW,
                                                ReconStatus.DUPLICATE_SUSPECT)
                             or t.category_confidence < 0.55),
        } for t in rows],
        "facets": _facets(db, ctx.business_id),
    })


def _facets(db, business_id: str) -> dict:
    cats = db.execute(select(Transaction.category, func.count())
                      .where(Transaction.business_id == business_id)
                      .group_by(Transaction.category)).all()
    rec = db.execute(select(Transaction.recon_status, func.count())
                     .where(Transaction.business_id == business_id)
                     .group_by(Transaction.recon_status)).all()
    return {"categories": [{"value": c, "count": n} for c, n in sorted(cats, key=lambda x: -x[1])],
            "recon_status": [{"value": c, "count": n} for c, n in rec]}


@router.get("/transactions/{txn_id}")
def get_transaction(txn_id: str, db: DbDep, ctx: Tenant):
    t = db.get(Transaction, txn_id)
    if not t or t.business_id != ctx.business_id:
        raise HTTPException(404, "Transaction not found")
    allocs = db.scalars(select(Allocation).where(Allocation.transaction_id == t.id)).all()
    inv = {i.id: i for i in db.scalars(select(Invoice).where(
        Invoice.id.in_([a.invoice_id for a in allocs]))).all()} if allocs else {}
    cp = db.get(Counterparty, t.counterparty_id) if t.counterparty_id else None
    return jsonable({
        "id": t.id, "date": t.value_date.isoformat(), "narration": t.narration,
        "reference_no": t.reference_no, "direction": t.direction,
        "amount": money(t.amount_paise), "category": t.category,
        "category_confidence": t.category_confidence, "category_rule": t.category_source,
        "counterparty": {"id": cp.id, "name": cp.name} if cp else None,
        "evidence": t.evidence, "recon_status": t.recon_status,
        "gross": money(t.gross_paise) if t.gross_paise else None,
        "fee": money(t.fee_paise) if t.fee_paise else None,
        "duplicate_of": t.duplicate_of,
        "allocations": [{"invoice_id": a.invoice_id,
                         "invoice_no": inv[a.invoice_id].invoice_no if a.invoice_id in inv else None,
                         "amount": money(a.amount_paise), "method": a.method,
                         "confidence": a.confidence, "rationale": a.rationale}
                        for a in allocs],
        "provenance": {"source_system": t.source_system, "source_ref": t.source_ref,
                       "import_batch_id": t.import_batch_id,
                       "raw": t.raw_json, "transform_log": t.transform_log_json},
    })


class TxnPatch(BaseModel):
    category: str | None = None
    counterparty_id: str | None = None
    recon_status: str | None = None
    narration: str | None = None
    mark_not_duplicate: bool = False


@router.patch("/transactions/{txn_id}")
def patch_transaction(txn_id: str, body: TxnPatch, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    t = db.get(Transaction, txn_id)
    if not t or t.business_id != ctx.business_id:
        raise HTTPException(404, "Transaction not found")
    log = list(t.transform_log_json or [])
    changed = {}
    if body.category:
        changed["category"] = [t.category, body.category]
        t.category, t.category_confidence, t.category_source = body.category, 1.0, "owner"
        # An owner correction is verified evidence; the classifier was not.
        t.evidence = Evidence.VERIFIED_ACTUAL
    if body.counterparty_id is not None:
        cp = db.get(Counterparty, body.counterparty_id)
        if body.counterparty_id and (not cp or cp.business_id != ctx.business_id):
            raise HTTPException(404, "Counterparty not found")
        changed["counterparty_id"] = [t.counterparty_id, body.counterparty_id]
        t.counterparty_id = body.counterparty_id or None
    if body.recon_status:
        changed["recon_status"] = [t.recon_status, body.recon_status]
        t.recon_status = body.recon_status
    if body.narration:
        changed["narration"] = [t.narration[:60], body.narration[:60]]
        t.narration = body.narration
    if body.mark_not_duplicate:
        changed["duplicate_of"] = [t.duplicate_of, None]
        t.duplicate_of = None
        if t.recon_status == ReconStatus.DUPLICATE_SUSPECT:
            t.recon_status = ReconStatus.UNRECONCILED
    log.append({"step": "owner_correction", "by": ctx.user.id, "changes": changed})
    t.transform_log_json = log
    audit(db, ctx, "transaction.update", entity="transaction", entity_id=t.id, detail=changed)
    db.commit()
    invalidate(ctx.business_id)
    return get_transaction(txn_id, db, ctx)


@router.get("/invoices")
def list_invoices(db: DbDep, ctx: Tenant, as_of: AsOf,
                  kind: str = Query(InvoiceKind.SALES),
                  status: str | None = None, counterparty_id: str | None = None,
                  overdue_only: bool = False, q: str | None = None,
                  sort: str = Query("due_asc", pattern="^(due_asc|due_desc|amount_desc|amount_asc)$"),
                  page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    stmt = select(Invoice).where(Invoice.business_id == ctx.business_id,
                                 Invoice.kind == kind, Invoice.issue_date <= as_of)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if counterparty_id:
        stmt = stmt.where(Invoice.counterparty_id == counterparty_id)
    if overdue_only:
        stmt = stmt.where(Invoice.due_date < as_of,
                          Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED]))
    if q:
        stmt = stmt.where(Invoice.invoice_no.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {"due_asc": Invoice.due_date.asc(), "due_desc": Invoice.due_date.desc(),
             "amount_desc": Invoice.total_paise.desc(),
             "amount_asc": Invoice.total_paise.asc()}[sort]
    rows = db.scalars(stmt.order_by(order, Invoice.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    names = {c.id: c.name for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == ctx.business_id)).all()}
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({
        "total": total, "page": page, "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": [{
            "id": i.id, "invoice_no": i.invoice_no, "kind": i.kind,
            "counterparty_id": i.counterparty_id,
            "counterparty": names.get(i.counterparty_id),
            "issue_date": i.issue_date.isoformat(), "due_date": i.due_date.isoformat(),
            "credit_days": i.credit_days, "days_past_due": (as_of - i.due_date).days,
            "total": money(i.total_paise), "settled": money(i.settled_paise),
            "outstanding": money(i.outstanding_paise),
            "taxable": money(i.taxable_paise), "tax": money(i.tax_paise),
            "status": i.status, "evidence": i.evidence,
            "prediction": b.predictions.get(i.id),
        } for i in rows],
    })


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, db: DbDep, ctx: Tenant, as_of: AsOf):
    i = db.get(Invoice, invoice_id)
    if not i or i.business_id != ctx.business_id:
        raise HTTPException(404, "Invoice not found")
    allocs = db.scalars(select(Allocation).where(Allocation.invoice_id == i.id)).all()
    txns = {t.id: t for t in db.scalars(select(Transaction).where(
        Transaction.id.in_([a.transaction_id for a in allocs]))).all()} if allocs else {}
    cp = db.get(Counterparty, i.counterparty_id)
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({
        "id": i.id, "invoice_no": i.invoice_no, "kind": i.kind,
        "counterparty": {"id": cp.id, "name": cp.name, "credit_days": cp.credit_days,
                         "msme_class": cp.msme_class} if cp else None,
        "issue_date": i.issue_date.isoformat(), "due_date": i.due_date.isoformat(),
        "days_past_due": (as_of - i.due_date).days,
        "total": money(i.total_paise), "taxable": money(i.taxable_paise),
        "tax": money(i.tax_paise), "settled": money(i.settled_paise),
        "outstanding": money(i.outstanding_paise), "status": i.status,
        "gst_rate": i.gst_rate, "evidence": i.evidence,
        "payments": [{"transaction_id": a.transaction_id,
                      "date": txns[a.transaction_id].value_date.isoformat()
                              if a.transaction_id in txns else None,
                      "amount": money(a.amount_paise), "method": a.method,
                      "confidence": a.confidence, "rationale": a.rationale}
                     for a in allocs],
        "prediction": b.predictions.get(i.id),
    })


@router.get("/customers")
def customers(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(),
                     "customers": [c.dict() for c in b.behaviour],
                     "concentration": b.concentration,
                     "correlation": b.correlation})


@router.get("/customers/{cp_id}")
def customer_detail(cp_id: str, db: DbDep, ctx: Tenant, as_of: AsOf):
    cp = db.get(Counterparty, cp_id)
    if not cp or cp.business_id != ctx.business_id:
        raise HTTPException(404, "Counterparty not found")
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    beh = next((c for c in b.behaviour if c.counterparty_id == cp_id), None)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == ctx.business_id, Invoice.counterparty_id == cp_id,
        Invoice.issue_date <= as_of).order_by(Invoice.issue_date.desc()).limit(80)).all()
    monthly: dict[str, dict] = {}
    for i in invs:
        k = i.issue_date.strftime("%Y-%m")
        m = monthly.setdefault(k, {"month": k, "billed_paise": 0, "count": 0,
                                   "settled_count": 0, "delay_sum": 0.0})
        m["billed_paise"] += i.total_paise
        m["count"] += 1
        if i.settled_date:
            m["settled_count"] += 1
            m["delay_sum"] += (i.settled_date - i.due_date).days
    for m in monthly.values():
        m["mean_delay_days"] = round(m["delay_sum"] / m["settled_count"], 1) if m["settled_count"] else None
        m.pop("delay_sum")
    return jsonable({
        "counterparty": {"id": cp.id, "name": cp.name, "type": cp.party_type,
                         "sector": cp.sector, "region": cp.region, "gstin": cp.gstin,
                         "credit_days": cp.credit_days, "msme_class": cp.msme_class,
                         "credit_limit": money(cp.credit_limit_paise),
                         "contact_name": cp.contact_name, "contact_phone": cp.contact_phone},
        "behaviour": beh.dict() if beh else None,
        "monthly": [monthly[k] for k in sorted(monthly)],
        "invoices": [{"id": i.id, "invoice_no": i.invoice_no,
                      "issue_date": i.issue_date.isoformat(),
                      "due_date": i.due_date.isoformat(),
                      "settled_date": i.settled_date.isoformat() if i.settled_date else None,
                      "delay_days": (i.settled_date - i.due_date).days if i.settled_date else None,
                      "total": money(i.total_paise),
                      "outstanding": money(i.outstanding_paise), "status": i.status,
                      "prediction": b.predictions.get(i.id)} for i in invs[:40]],
    })


@router.get("/suppliers")
def suppliers(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(),
                     "suppliers": [s.dict() for s in b.supplier_profiles],
                     "payment_calendar": b.payment_calendar,
                     "msmed": b.msmed,
                     "ageing": b.ageing_ap})


@router.get("/receivables")
def receivables(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(), "ageing": b.ageing_ar,
                     "collection_list": b.collection_list,
                     "customers": [c.dict() for c in b.behaviour],
                     "total": money(b.ageing_ar["total_paise"]),
                     "overdue": money(b.ageing_ar["overdue_paise"])})


@router.get("/payables")
def payables(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(), "ageing": b.ageing_ap,
                     "calendar": b.payment_calendar, "msmed": b.msmed,
                     "suppliers": [s.dict() for s in b.supplier_profiles]})


@router.get("/compliance")
def compliance(db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.analytics.obligations import next_gst_deadline
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({
        "as_of": as_of.isoformat(),
        "calendar": b.obligations, "coverage": b.coverage, "msmed": b.msmed,
        "next_gst": next_gst_deadline(as_of),
        "rules": [
            {"code": "MSMED s.15",
             "summary": ("Payment to a registered micro or small enterprise is due within "
                         "the agreed period, which cannot exceed 45 days; with no written "
                         "agreement the limit is 15 days. Medium enterprises are outside "
                         "the rule."),
             "runway_handling": "Open purchase invoices are scheduled at the earlier of the "
                                "contractual due date and the statutory deadline."},
            {"code": "Income-tax s.43B(h)",
             "summary": ("An amount owed to a micro or small enterprise is deductible only "
                         "in the year it is actually paid. Unlike other 43B items, paying "
                         "before the return due date does not preserve the earlier year."),
             "runway_handling": "Exposure is reported; the scenario engine refuses to defer "
                                "these invoices unless the owner explicitly overrides it."},
            {"code": "GSTR-3B",
             "summary": "Monthly filers pay by the 20th of the following month.",
             "runway_handling": ("Liability is estimated as output tax on recorded sales "
                                 "less input credit on recorded purchases, and is labelled "
                                 "an estimate until confirmed against a filed return.")},
        ],
        "disclaimer": ("RUNWAY surfaces deadlines and exposure from your own ledger. It is "
                       "not tax advice. Confirm supplier Udyam registration and filed "
                       "liabilities before relying on these figures."),
    })


@router.get("/accounts")
def accounts(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    return jsonable({"as_of": as_of.isoformat(), "position": b.position.dict(),
                     "working_capital": b.working_capital, "flow_30d": b.flow_30d})


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str = AccountKind.CURRENT
    bank_name: str | None = Field(default=None, max_length=120)
    masked_number: str | None = Field(default=None, max_length=40)
    opening_balance_paise: int = 0
    overdraft_limit_paise: int = Field(default=0, ge=0)
    restricted_paise: int = Field(default=0, ge=0)
    opening_date: date | None = None


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    bank_name: str | None = Field(default=None, max_length=120)
    masked_number: str | None = Field(default=None, max_length=40)
    opening_balance_paise: int | None = None
    overdraft_limit_paise: int | None = Field(default=None, ge=0)
    restricted_paise: int | None = Field(default=None, ge=0)


@router.post("/accounts", status_code=201)
def create_account(body: AccountIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    ctx.require(Role.MANAGER)
    valid_kinds = {k.value for k in AccountKind}
    if body.kind not in valid_kinds:
        raise HTTPException(422, f"kind must be one of {sorted(valid_kinds)}")
    acc = Account(
        id=_uid(), business_id=ctx.business_id,
        name=body.name.strip(), kind=body.kind,
        bank_name=body.bank_name.strip() if body.bank_name else None,
        masked_number=body.masked_number.strip() if body.masked_number else None,
        opening_balance_paise=body.opening_balance_paise,
        overdraft_limit_paise=body.overdraft_limit_paise,
        restricted_paise=body.restricted_paise,
        opening_date=body.opening_date or (as_of - timedelta(days=365)),
        source_system="manual",
    )
    db.add(acc)
    audit(db, ctx, "account.create", entity="account", entity_id=acc.id,
          detail={"name": acc.name, "opening_balance_paise": acc.opening_balance_paise})
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"id": acc.id, "name": acc.name, "kind": acc.kind,
                     "opening_balance": money(acc.opening_balance_paise),
                     "overdraft_limit": money(acc.overdraft_limit_paise),
                     "restricted": money(acc.restricted_paise)})


@router.patch("/accounts/{account_id}")
def patch_account(account_id: str, body: AccountPatch, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    acc = db.get(Account, account_id)
    if not acc or acc.business_id != ctx.business_id:
        raise HTTPException(404, "Account not found")
    changed = {}
    for field, value in body.model_dump(exclude_none=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(acc, field, value)
        changed[field] = value
    audit(db, ctx, "account.update", entity="account", entity_id=acc.id, detail=changed)
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"id": acc.id, "name": acc.name, "kind": acc.kind,
                     "opening_balance": money(acc.opening_balance_paise),
                     "overdraft_limit": money(acc.overdraft_limit_paise),
                     "restricted": money(acc.restricted_paise)})


class InvoiceIn(BaseModel):
    kind: str = InvoiceKind.SALES
    counterparty_name: str = Field(min_length=1, max_length=200)
    invoice_no: str = Field(min_length=1, max_length=60)
    issue_date: date
    due_date: date | None = None
    credit_days: int = Field(default=30, ge=0, le=365)
    total_paise: int = Field(gt=0)
    tax_paise: int | None = Field(default=None, ge=0)
    settled_paise: int = Field(default=0, ge=0)
    settled_date: date | None = None
    msme_class: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    has_written_agreement: bool = True
    notes: str | None = None


@router.post("/invoices", status_code=201)
def create_invoice(body: InvoiceIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.ledger.normalise import party_key
    from app.ledger.reconciliation import refresh_overdue
    ctx.require(Role.MANAGER)
    if body.kind not in (InvoiceKind.SALES, InvoiceKind.PURCHASE):
        raise HTTPException(422, "kind must be 'sales' or 'purchase'")
    if body.msme_class and body.msme_class not in ("micro", "small", "medium", "none"):
        raise HTTPException(422, "msme_class must be micro, small, medium or none")
    inv_no = body.invoice_no.strip()
    dup = db.scalar(select(Invoice).where(
        Invoice.business_id == ctx.business_id,
        Invoice.kind == body.kind,
        Invoice.invoice_no == inv_no,
    ))
    if dup:
        raise HTTPException(409, f"{body.kind} invoice '{inv_no}' already exists")

    name = body.counterparty_name.strip()
    key = party_key(name)
    cp = db.scalar(select(Counterparty).where(
        Counterparty.business_id == ctx.business_id,
        Counterparty.normalised_name == key,
    ))
    if cp is None:
        cp = Counterparty(
            id=_uid(), business_id=ctx.business_id, name=name, normalised_name=key,
            party_type="customer" if body.kind == InvoiceKind.SALES else "supplier",
            gstin=body.gstin.strip().upper() if body.gstin else None,
            msme_class=body.msme_class,
            credit_days=body.credit_days,
        )
        db.add(cp)
        db.flush()
    else:
        if body.msme_class and not cp.msme_class:
            cp.msme_class = body.msme_class
        if body.gstin and not cp.gstin:
            cp.gstin = body.gstin.strip().upper()

    due = body.due_date or (body.issue_date + timedelta(days=body.credit_days))
    credit_days = max(0, (due - body.issue_date).days)
    if body.tax_paise is not None:
        tax = min(body.total_paise, body.tax_paise)
        taxable = body.total_paise - tax
    else:
        taxable = round(body.total_paise / 1.18)
        tax = body.total_paise - taxable
    settled = min(body.total_paise, body.settled_paise)
    settled_date = body.settled_date
    if settled >= body.total_paise:
        status = InvoiceStatus.PAID
        settled_date = settled_date or due
    elif settled > 0:
        status = InvoiceStatus.PART_PAID
    else:
        status = InvoiceStatus.OVERDUE if due < as_of else InvoiceStatus.OPEN

    inv = Invoice(
        id=_uid(), business_id=ctx.business_id, counterparty_id=cp.id,
        kind=body.kind, invoice_no=inv_no, issue_date=body.issue_date, due_date=due,
        credit_days=credit_days, taxable_paise=taxable, tax_paise=tax,
        total_paise=body.total_paise, settled_paise=settled, written_off_paise=0,
        status=status, settled_date=settled_date,
        has_written_agreement=body.has_written_agreement,
        source_system="manual", evidence=Evidence.OWNER_ESTIMATE, notes=body.notes,
    )
    db.add(inv)
    db.flush()
    refresh_overdue(db, ctx.business_id, as_of)
    audit(db, ctx, "invoice.create", entity="invoice", entity_id=inv.id,
          detail={"kind": inv.kind, "invoice_no": inv.invoice_no, "total_paise": inv.total_paise})
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"id": inv.id, "invoice_no": inv.invoice_no, "kind": inv.kind,
                     "counterparty": cp.name, "status": inv.status,
                     "total": money(inv.total_paise), "outstanding": money(inv.outstanding_paise)})


class ObligationIn(BaseModel):
    kind: str = ObligationKind.OTHER
    label: str = Field(min_length=1, max_length=200)
    due_date: date
    amount_paise: int = Field(gt=0)
    is_recurring: bool = False
    recurrence: str | None = "monthly"
    reserve_cash: bool = True


@router.post("/obligations", status_code=201)
def create_obligation(body: ObligationIn, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    valid_kinds = {k.value for k in ObligationKind}
    if body.kind not in valid_kinds:
        raise HTTPException(422, f"kind must be one of {sorted(valid_kinds)}")
    ob = Obligation(
        id=_uid(), business_id=ctx.business_id, kind=body.kind,
        label=body.label.strip(), due_date=body.due_date,
        amount_paise=body.amount_paise, evidence=Evidence.OWNER_ESTIMATE,
        is_recurring=body.is_recurring,
        recurrence=body.recurrence if body.is_recurring else None,
        reserve_cash=body.reserve_cash, source_system="manual",
    )
    db.add(ob)
    audit(db, ctx, "obligation.create", entity="obligation", entity_id=ob.id,
          detail={"kind": ob.kind, "label": ob.label, "amount_paise": ob.amount_paise})
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"id": ob.id, "kind": ob.kind, "label": ob.label,
                     "due_date": ob.due_date.isoformat(), "amount": money(ob.amount_paise),
                     "is_recurring": ob.is_recurring, "reserve_cash": ob.reserve_cash})


class LoanIn(BaseModel):
    lender: str = Field(min_length=1, max_length=160)
    kind: str = "term"
    principal_paise: int = Field(gt=0)
    outstanding_paise: int | None = Field(default=None, ge=0)
    annual_rate: float = Field(default=0.14, ge=0, le=1)
    emi_paise: int = Field(gt=0)
    emi_day: int = Field(default=5, ge=1, le=28)


@router.post("/loans", status_code=201)
def create_loan(body: LoanIn, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    ln = Loan(
        id=_uid(), business_id=ctx.business_id, lender=body.lender.strip(),
        kind=body.kind, principal_paise=body.principal_paise,
        outstanding_paise=body.outstanding_paise if body.outstanding_paise is not None else body.principal_paise,
        annual_rate=body.annual_rate, emi_paise=body.emi_paise, emi_day=body.emi_day,
        is_active=True,
    )
    db.add(ln)
    audit(db, ctx, "loan.create", entity="loan", entity_id=ln.id,
          detail={"lender": ln.lender, "emi_paise": ln.emi_paise})
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"id": ln.id, "lender": ln.lender, "emi": money(ln.emi_paise),
                     "outstanding": money(ln.outstanding_paise)})


class TransactionIn(BaseModel):
    account_id: str | None = None
    value_date: date
    amount_paise: int = Field(gt=0)
    direction: str = Direction.CREDIT
    narration: str = Field(min_length=1, max_length=500)
    reference_no: str | None = Field(default=None, max_length=80)
    category: str | None = None
    counterparty_name: str | None = Field(default=None, max_length=200)


@router.post("/transactions", status_code=201)
def create_transaction(body: TransactionIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.ledger.classifier import classify
    from app.ledger.entities import resolve_counterparty
    from app.ledger.normalise import fingerprint
    from app.ledger.reconciliation import apply_match, match_transaction, refresh_overdue

    ctx.require(Role.MANAGER)
    if body.direction not in (Direction.CREDIT, Direction.DEBIT):
        raise HTTPException(422, "direction must be 'credit' or 'debit'")

    acc = None
    if body.account_id:
        acc = db.get(Account, body.account_id)
        if not acc or acc.business_id != ctx.business_id:
            raise HTTPException(404, "Account not found")
    else:
        acc = db.scalar(select(Account).where(
            Account.business_id == ctx.business_id, Account.is_active.is_(True)))
        if acc is None:
            acc = Account(
                id=_uid(), business_id=ctx.business_id, name="Primary Bank Account",
                kind=AccountKind.CURRENT, opening_balance_paise=0,
                opening_date=as_of - timedelta(days=365), source_system="manual",
            )
            db.add(acc)
            db.flush()

    cp_id, cp_conf, cp_why = resolve_counterparty(
        db, ctx.business_id, f"{body.narration} {body.counterparty_name or ''}",
        body.direction)
    if cp_id is None and body.counterparty_name and body.counterparty_name.strip():
        from app.ledger.normalise import party_key
        cname = body.counterparty_name.strip()
        ckey = party_key(cname)
        cp = db.scalar(select(Counterparty).where(
            Counterparty.business_id == ctx.business_id, Counterparty.normalised_name == ckey))
        if cp is None:
            cp = Counterparty(
                id=_uid(), business_id=ctx.business_id, name=cname, normalised_name=ckey,
                party_type="customer" if body.direction == Direction.CREDIT else "supplier",
                credit_days=30,
            )
            db.add(cp)
            db.flush()
        cp_id, cp_conf, cp_why = cp.id, 1.0, "created from manual entry"
    cp_type = None
    if cp_id:
        cp = db.get(Counterparty, cp_id)
        cp_type = cp.party_type if cp else None

    if body.category:
        cat, conf, rule = body.category, 1.0, "owner"
        evidence = Evidence.VERIFIED_ACTUAL
    else:
        cat, conf, rule = classify(body.narration, body.direction, counterparty_type=cp_type)
        evidence = Evidence.OWNER_ESTIMATE

    txn = Transaction(
        id=_uid(), business_id=ctx.business_id, account_id=acc.id,
        counterparty_id=cp_id, source_system="manual",
        source_ref=body.reference_no, value_date=body.value_date,
        posting_date=body.value_date, amount_paise=body.amount_paise,
        direction=body.direction, narration=body.narration.strip(),
        reference_no=body.reference_no.strip() if body.reference_no else None,
        category=cat, category_confidence=conf, category_source=rule,
        evidence=evidence, recon_status=ReconStatus.UNRECONCILED,
        allocated_paise=0,
        transform_log_json=[
            {"step": "manual_entry", "by": ctx.user.id},
            {"step": "resolve_counterparty", "result": cp_why, "confidence": round(cp_conf, 2)},
            {"step": "classify", "category": cat, "confidence": conf, "rule": rule},
        ],
    )
    txn.fingerprint = fingerprint(
        business_id=ctx.business_id, account_id=acc.id, value_date=body.value_date,
        amount_paise=body.amount_paise, direction=body.direction,
        reference_no=txn.reference_no, narration=txn.narration,
    )
    db.add(txn)
    db.flush()
    res = match_transaction(db, txn)
    apply_match(db, txn, res)
    refresh_overdue(db, ctx.business_id, as_of)
    audit(db, ctx, "transaction.create", entity="transaction", entity_id=txn.id,
          detail={"direction": txn.direction, "amount_paise": txn.amount_paise, "category": txn.category})
    db.commit()
    invalidate(ctx.business_id)
    return get_transaction(txn.id, db, ctx)
