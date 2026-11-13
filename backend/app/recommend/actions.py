"""Marking a cash recommendation "done" records the money in the ledger.

When the owner says "done" on *Collect overdue invoices* or *Pay MSME
suppliers*, they are telling RUNWAY the money moved. That is recorded the
same way as a manual entry: one ledger row per invoice the recommendation
named, for that invoice's open balance, matched to the invoice so it closes.
Cash, receivables and payables update immediately.

The rows are marked ``owner_estimate`` evidence and ``source_system =
"recommendation"`` - owner-confirmed, not yet bank-verified - and they are
grouped in one Import-history entry, so Undo (or Revert) removes them
exactly. When the real bank statement arrives with the same payment, the
duplicate check flags it rather than counting the money twice.
"""
from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select

from app.core.enums import (
    Direction, Evidence, InvoiceKind, ReconStatus, TxnCategory,
)
from app.ledger.asof import outstanding_at
from app.ledger.normalise import fingerprint
from app.ledger.reconciliation import apply_match, match_transaction, refresh_overdue
from app.models import Account, Counterparty, ImportBatch, Invoice, Transaction, _uid

# code -> (direction, invoice kind, category, verb)
CASH_ACTIONS = {
    "collect_overdue": (Direction.CREDIT, InvoiceKind.SALES, TxnCategory.CUSTOMER_RECEIPT,
                        "received from"),
    "pay_msme_suppliers": (Direction.DEBIT, InvoiceKind.PURCHASE,
                           TxnCategory.SUPPLIER_PAYMENT, "paid to"),
}
_REF = re.compile(r"\b((?:INV|PUR)-[A-Z0-9-]+)\b", re.I)


def _invoice_numbers(rec) -> list[str]:
    seen: list[str] = []
    for e in rec.trigger_evidence_json or []:
        for m in _REF.finditer(f"{e.get('label', '')} {e.get('value', '')}"):
            no = m.group(1).upper()
            if no not in seen:
                seen.append(no)
    return seen


def record_done(db, *, business_id: str, rec, as_of: date, user_id: str) -> dict:
    spec = CASH_ACTIONS.get(rec.code)
    if spec is None:
        return {"recorded": False,
                "reason": "This action moves no money, so there is nothing to record in cash."}
    direction, kind, category, verb = spec
    acct = db.scalar(select(Account).where(Account.business_id == business_id,
                                           Account.is_active.is_(True),
                                           Account.kind == "current")) \
        or db.scalar(select(Account).where(Account.business_id == business_id,
                                           Account.is_active.is_(True)))
    if acct is None:
        return {"recorded": False, "reason": "No bank account to record the money in."}

    batch = ImportBatch(id=_uid(), business_id=business_id, adapter="recommendation",
                        filename=f"Marked done: {rec.title}"[:300], status="imported",
                        rows_seen=0, report_json={"recommendation": rec.code,
                                                  "evidence": "owner_confirmed"})
    db.add(batch)
    db.flush()
    rows, total = [], 0
    for no in _invoice_numbers(rec):
        inv = db.scalar(select(Invoice).where(Invoice.business_id == business_id,
                                              Invoice.kind == kind, Invoice.invoice_no == no))
        if inv is None:
            continue
        amount = outstanding_at(inv, as_of)
        if amount <= 0:
            continue
        cp = db.get(Counterparty, inv.counterparty_id)
        name = cp.name if cp else "counterparty"
        narration = f"Owner confirmed: {verb} {name} for {no} (marked done in RUNWAY)"
        t = Transaction(
            id=_uid(), business_id=business_id, account_id=acct.id,
            import_batch_id=batch.id, source_system="recommendation",
            source_ref=f"REC-{rec.code}", value_date=as_of, posting_date=as_of,
            amount_paise=amount, direction=direction, currency="INR",
            narration=narration, reference_no=f"DONE-{no}",
            evidence=Evidence.OWNER_ESTIMATE, recon_status=ReconStatus.UNRECONCILED,
            allocated_paise=0, counterparty_id=inv.counterparty_id,
            category=category, category_confidence=0.95,
            category_source=f"recommendation '{rec.code}' marked done",
            raw_json={"recommendation": rec.code, "invoice_no": no, "by": user_id},
            transform_log_json=[{"step": "recommendation_done", "code": rec.code,
                                 "invoice_no": no, "by": user_id}])
        t.fingerprint = fingerprint(business_id=business_id, account_id=acct.id,
                                    value_date=as_of, amount_paise=amount,
                                    direction=direction, reference_no=t.reference_no,
                                    narration=narration)
        db.add(t)
        db.flush()
        apply_match(db, t, match_transaction(db, t))
        rows.append({"invoice_no": no, "counterparty": name, "amount_paise": amount})
        total += amount
    batch.rows_seen = batch.rows_imported = len(rows)
    batch.report_json = {**batch.report_json, "rows": rows, "total_paise": total}
    refresh_overdue(db, business_id, as_of)
    return {"recorded": bool(rows), "batch_id": batch.id, "rows": rows,
            "total_paise": total, "direction": direction,
            "reason": None if rows else "Every invoice it named is already settled."}


def undo_done(db, *, business_id: str, code: str) -> dict:
    from app.integrations.service import revert_batch
    undone = 0
    for b in db.scalars(select(ImportBatch).where(ImportBatch.business_id == business_id,
                                                  ImportBatch.adapter == "recommendation",
                                                  ImportBatch.status != "reverted")).all():
        if (b.report_json or {}).get("recommendation") == code:
            revert_batch(db, b)
            undone += 1
    return {"undone_entries": undone}
