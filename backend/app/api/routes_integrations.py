from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit, resolved_as_of
from app.core.enums import Role
from app.digital_twin.digital_twin_service import invalidate
from app.integrations.history import import_with_impact
from app.ledger.reconciliation import refresh_overdue
from app.integrations.service import catalogue, import_file
from app.models import Account, ImportBatch, Transaction, _uid

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
AsOf = Annotated[date, Depends(resolved_as_of)]
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


@router.get("")
def list_integrations():
    return catalogue()


@router.get("/batches")
def batches(db: DbDep, ctx: Tenant, limit: int = Query(30, le=200)):
    rows = db.scalars(select(ImportBatch).where(ImportBatch.business_id == ctx.business_id)
                      .order_by(ImportBatch.created_at.desc()).limit(limit)).all()
    return jsonable({"batches": [{
        "id": b.id, "adapter": b.adapter, "filename": b.filename, "status": b.status,
        "rows_seen": b.rows_seen, "rows_imported": b.rows_imported,
        "rows_duplicate": b.rows_duplicate, "rows_rejected": b.rows_rejected,
        "created_at": b.created_at.isoformat(), "report": b.report_json,
        "impact": (b.report_json or {}).get("impact"),
        "errors": (b.errors_json or [])[:20]} for b in rows]})


@router.post("/batches/{batch_id}/revert")
def revert(batch_id: str, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Undo a wrong upload (wrong file, wrong account, wrong business)."""
    ctx.require(Role.MANAGER)
    b = db.get(ImportBatch, batch_id)
    if not b or b.business_id != ctx.business_id:
        raise HTTPException(404, "Import not found")
    if b.status == "reverted":
        raise HTTPException(409, "This upload was already reverted")
    from app.integrations.service import revert_batch
    res = revert_batch(db, b)
    refresh_overdue(db, ctx.business_id, as_of)
    audit(db, ctx, "import.revert", entity="import_batch", entity_id=b.id, detail=res)
    db.commit()
    invalidate(ctx.business_id)
    return jsonable({"batch_id": b.id, "status": b.status, **res})


@router.get("/batches/{batch_id}")
def batch_detail(batch_id: str, db: DbDep, ctx: Tenant,
                 limit: int = Query(200, ge=1, le=2000)):
    """One past upload: its report, what it changed, and the rows it added."""
    b = db.get(ImportBatch, batch_id)
    if not b or b.business_id != ctx.business_id:
        raise HTTPException(404, "Import not found")
    txns = db.scalars(select(Transaction).where(Transaction.import_batch_id == b.id)
                      .order_by(Transaction.value_date).limit(limit)).all()
    total = db.scalar(select(func.count()).select_from(Transaction)
                      .where(Transaction.import_batch_id == b.id))
    return jsonable({
        "id": b.id, "adapter": b.adapter, "filename": b.filename, "status": b.status,
        "created_at": b.created_at.isoformat(),
        "rows_seen": b.rows_seen, "rows_imported": b.rows_imported,
        "rows_duplicate": b.rows_duplicate, "rows_rejected": b.rows_rejected,
        "errors": (b.errors_json or [])[:100],
        "impact": (b.report_json or {}).get("impact"),
        "date_range": [txns[0].value_date.isoformat(), txns[-1].value_date.isoformat()]
        if txns else None,
        "transactions_total": total,
        "transactions": [{
            "id": t.id, "date": t.value_date.isoformat(), "narration": t.narration,
            "reference": t.reference_no, "direction": t.direction,
            "amount": money(t.amount_paise), "category": t.category,
            "recon_status": t.recon_status} for t in txns],
    })


@router.post("/import")
async def do_import(db: DbDep, ctx: Tenant, as_of: AsOf,
                    adapter: Annotated[str, Form()],
                    account_id: Annotated[str, Form()],
                    dry_run: Annotated[bool, Form()] = True,
                    file: UploadFile = File(...)):
    ctx.require(Role.MANAGER)
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB limit")
    if not content:
        raise HTTPException(422, "Empty file")
    try:
        if dry_run:
            result = import_file(db, business_id=ctx.business_id, account_id=account_id,
                                 adapter_key=adapter, content=content,
                                 filename=file.filename or "", dry_run=True, today=as_of)
        else:
            # Records the headline figures before and after on the batch, so
            # every past upload keeps a record of what it changed.
            result = import_with_impact(db, import_file, business_id=ctx.business_id,
                                        as_of=as_of, account_id=account_id,
                                        adapter_key=adapter, content=content,
                                        filename=file.filename or "", dry_run=False)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not dry_run:
        audit(db, ctx, "import.commit", entity="import_batch",
              entity_id=result["batch_id"],
              detail={"adapter": adapter, "rows": result["rows_imported"]})
        db.commit()
        invalidate(ctx.business_id)
    else:
        db.rollback()
    return jsonable(result)


@router.get("/accounts")
def importable_accounts(db: DbDep, ctx: Tenant):
    rows = db.scalars(select(Account).where(Account.business_id == ctx.business_id,
                                            Account.is_active.is_(True))).all()
    if not rows:
        # A newly registered business has no account, so nothing could be
        # imported. Give it one; its true opening date is unknown, so it is
        # set early enough not to refuse the owner's past statements.
        a = Account(id=_uid(), business_id=ctx.business_id, name="Current account",
                    kind="current", currency="INR", opening_balance_paise=0,
                    opening_date=date(2000, 1, 1), source_system="default")
        db.add(a)
        db.commit()
        rows = [a]
    return jsonable({"accounts": [{"id": a.id, "name": a.name, "kind": a.kind,
                                   "bank_name": a.bank_name,
                                   "masked_number": a.masked_number,
                                   "source_system": a.source_system} for a in rows]})


@router.get("/sample/{adapter}")
def sample_file(adapter: str):
    """A ready-made sample so the import flow can be demonstrated immediately."""
    samples = {
        "bank_csv": ("hdfc-sample-statement.csv",
                     "Date,Narration,Chq/Ref No,Withdrawal Amt,Deposit Amt,Closing Balance\n"
                     "05/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1807,NEFT993188210,,132346.00,845000.00\n"
                     "05/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1807,NEFT993188210,,132346.00,845000.00\n"
                     "06/11/2026,GST CHALLAN PMT-06 GSTR-3B OCT 2026,GST202610,269974.00,,575026.00\n"
                     "06/11/2026,NEFT DR-XYZ FOODS PVT LTD-PUR-5231,NEFT771209883,184500.00,,390526.00\n"
                     "07/11/2026,UPI/P2A/418822190034/PAYMENT,,,42000.00,432526.00\n"),
        "upi_settlement_csv": ("razorpay-settlement-sample.csv",
                               "Settlement Date,Payment Id,Gross Amount,Fee,Net Amount,Order Id\n"
                               "2026-11-05,RZP8811290034,50000.00,425.00,49575.00,INV-1812\n"
                               "2026-11-06,RZP8811290099,128400.00,1091.40,127308.60,INV-1816\n"),
        "gst_invoice_json": ("gstr1-b2b-sample.json",
                             '{"b2b":[{"ctin":"36AABCU9603R1ZX","inv":[{"inum":"INV-1899",'
                             '"idt":"2026-11-03","val":265500,"txval":225000,"iamt":40500}]}]}'),
        "tally_xml": ("tally-daybook-sample.xml",
                      '<ENVELOPE><BODY><TALLYMESSAGE><VOUCHER VCHTYPE="Receipt">'
                      '<DATE>20261105</DATE><VOUCHERNUMBER>RCT-204</VOUCHERNUMBER>'
                      '<PARTYLEDGERNAME>ABC Distributors</PARTYLEDGERNAME>'
                      '<NARRATION>Against INV-1807</NARRATION><AMOUNT>132346.00</AMOUNT>'
                      '</VOUCHER></TALLYMESSAGE></BODY></ENVELOPE>'),
    }
    if adapter == "pdf_invoice":
        # A PDF cannot be handed over as pasteable text, so explain how to
        # produce one rather than returning a 404 that reads like a bug.
        from app.integrations.pdf_invoice import ocr_available
        return {
            "filename": None, "content": None,
            "binary": True,
            "note": ("PDF is a binary format, so there is no sample to paste. Use any "
                     "invoice PDF from your accounting software — RUNWAY reads the text "
                     "layer directly. Each extracted field is shown with its own "
                     "confidence before anything is written."),
            "ocr_available": ocr_available(),
            "ocr_note": ("Scanned PDFs will be OCR'd on this machine."
                         if ocr_available() else
                         "Scanned PDFs cannot be read here: install tesseract-ocr and "
                         "poppler-utils. Text-layer PDFs work without them."),
        }
    if adapter not in samples:
        raise HTTPException(404, "No sample available for that adapter")
    name, body = samples[adapter]
    return {"filename": name, "content": body,
            "note": ("The bank sample deliberately contains an exact duplicate row so "
                     "the duplicate detector can be seen working.")}
