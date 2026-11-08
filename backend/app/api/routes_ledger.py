"""Ledger surface: transactions, invoices, counterparties, compliance."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit
from app.core.enums import Direction, Evidence, InvoiceKind, InvoiceStatus, ReconStatus, Role
from app.digital_twin.digital_twin_service import get_bundle, invalidate
from app.models import Allocation, Counterparty, Invoice, Transaction

router = APIRouter(prefix="/api", tags=["ledger"])
AsOf = Annotated[date, Depends(today_param)]


@router.get("/transactions")
def list_transactions(
    db: DbDep, ctx: Tenant,
    q: str | None = Query(None, description="free text over narration and reference"),
    category: str | None = None, direction: str | None = None,
    recon_status: str | None = None, counterparty_id: str | None = None,
    account_id: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    min_paise: int | None = None, max_paise: int | None = None,
    needs_review: bool = False,
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|amount_desc|amount_asc)$"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(Transaction).where(Transaction.business_id == ctx.business_id)
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
