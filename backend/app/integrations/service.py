"""Import pipeline: parse -> dedupe -> resolve -> classify -> reconcile."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from app.core.enums import Evidence, InvoiceKind, InvoiceStatus, ReconStatus
from app.integrations import adapters as _adapters  # noqa: F401 (registers adapters)
from app.integrations import pdf_invoice as _pdf_invoice  # noqa: F401
from app.integrations.base import REGISTRY, NormalisedRow
from app.ledger.classifier import classify
from app.ledger.entities import resolve_counterparty
from app.ledger.normalise import detect_duplicate, fingerprint, mark_suspected_duplicate, party_key
from app.ledger.reconciliation import apply_match, match_transaction, refresh_overdue
from app.models import Account, Counterparty, ImportBatch, Invoice, Transaction, _uid


def import_file(db, *, business_id: str, account_id: str, adapter_key: str,
                content: bytes, filename: str = "", dry_run: bool = False,
                today: date | None = None) -> dict:
    adapter = REGISTRY.get(adapter_key)
    if adapter is None:
        raise ValueError(f"unknown adapter '{adapter_key}'")
    account = db.get(Account, account_id)
    if account is None or account.business_id != business_id:
        raise ValueError("account not found in this business")

    parsed, report = adapter.parse(content, filename=filename)
    batch = ImportBatch(id=_uid(), business_id=business_id, adapter=adapter_key,
                        filename=filename, status="parsed",
                        rows_seen=report.rows_seen, rows_rejected=report.rows_rejected,
                        errors_json=report.errors[:100])

    created_txn, created_inv, dup_hard, dup_soft = [], [], 0, 0
    preview: list[dict] = []
    cache: dict = {}
    # A file can repeat a row within itself. Checking only against the
    # database would let an in-file duplicate through on a dry run, where
    # nothing has been flushed yet.
    seen_in_batch: dict[str, int] = {}

    for item in parsed:
        if isinstance(item, NormalisedRow):
            row, kind = item, "transaction"
        elif isinstance(item, dict) and item.get("__type") == "transaction":
            row, kind = item["row"], "transaction"
        elif isinstance(item, dict) and item.get("__type") == "invoice":
            row, kind = item, "invoice"
        else:
            continue

        if kind == "invoice":
            inv, note = _build_invoice(db, business_id, row, cache)
            preview.append({"kind": "invoice", "invoice_no": inv.invoice_no,
                            "date": inv.issue_date.isoformat(),
                            "amount_paise": inv.total_paise, "note": note})
            if not dry_run:
                db.add(inv)
                created_inv.append(inv)
            continue

        txn = Transaction(
            id=_uid(), business_id=business_id, account_id=account_id,
            import_batch_id=batch.id, source_system=adapter_key,
            source_ref=row.reference_no, value_date=row.value_date,
            posting_date=row.posting_date or row.value_date,
            amount_paise=row.amount_paise, direction=row.direction,
            currency=row.currency, narration=row.narration,
            reference_no=row.reference_no, evidence=row.evidence,
            recon_status=ReconStatus.UNRECONCILED, allocated_paise=0,
            gross_paise=row.gross_paise, fee_paise=row.fee_paise,
            raw_json=row.raw,
            transform_log_json=[{"step": "parse", "adapter": adapter_key,
                                 "file": filename}])
        txn.fingerprint = fingerprint(
            business_id=business_id, account_id=account_id, value_date=row.value_date,
            amount_paise=row.amount_paise, direction=row.direction,
            reference_no=row.reference_no, narration=row.narration)

        is_dup, existing_id, reason = detect_duplicate(db, business_id, txn)
        if not is_dup and txn.fingerprint in seen_in_batch:
            if row.reference_no:
                is_dup = True
                existing_id = f"row {seen_in_batch[txn.fingerprint]} of this file"
                reason = "identical bank reference, amount and date earlier in this same file"
            else:
                existing_id = f"row {seen_in_batch[txn.fingerprint]} of this file"
                reason = "same date, amount and narration earlier in this same file"
        seen_in_batch.setdefault(txn.fingerprint, rep_index := (len(preview) + 1))
        if is_dup:
            dup_hard += 1
            preview.append({"kind": "duplicate_rejected", "date": row.value_date.isoformat(),
                            "amount_paise": row.amount_paise,
                            "narration": row.narration[:120], "reason": reason,
                            "existing_transaction_id": existing_id})
            continue
        if existing_id:
            dup_soft += 1
            mark_suspected_duplicate(txn, existing_id, reason)

        cp_id, cp_conf, cp_why = resolve_counterparty(
            db, business_id, f"{row.narration} {row.counterparty_hint or ''}",
            row.direction, cache=cache)
        txn.counterparty_id = cp_id
        cp_type = None
        if cp_id:
            cp = db.get(Counterparty, cp_id)
            cp_type = cp.party_type if cp else None
        cat, conf, rule = classify(row.narration, row.direction, counterparty_type=cp_type)
        txn.category, txn.category_confidence, txn.category_source = cat, conf, rule
        txn.transform_log_json = list(txn.transform_log_json) + [
            {"step": "resolve_counterparty", "result": cp_why, "confidence": round(cp_conf, 2)},
            {"step": "classify", "category": cat, "confidence": conf, "rule": rule}]

        preview.append({
            "kind": "transaction", "date": row.value_date.isoformat(),
            "direction": row.direction, "amount_paise": row.amount_paise,
            "narration": row.narration[:120], "category": cat,
            "category_confidence": conf, "category_rule": rule,
            "counterparty": (db.get(Counterparty, cp_id).name if cp_id else None),
            "counterparty_confidence": round(cp_conf, 2),
            "counterparty_reason": cp_why,
            "needs_review": conf < 0.55 or (existing_id is not None),
            "duplicate_suspect": existing_id is not None})
        if not dry_run:
            db.add(txn)
            created_txn.append(txn)

    batch.rows_imported = len(created_txn) + len(created_inv)
    batch.rows_duplicate = dup_hard + dup_soft
    batch.status = "preview" if dry_run else "imported"

    matched = 0
    if not dry_run:
        db.flush()
        for txn in created_txn:
            res = match_transaction(db, txn)
            apply_match(db, txn, res)
            if res.status in (ReconStatus.MATCHED, ReconStatus.PARTIALLY_MATCHED):
                matched += 1
        refresh_overdue(db, business_id, today or date.today())
        db.add(batch)
        db.flush()

    batch.report_json = {
        "detected_format": report.detected_format,
        "column_mapping": report.column_mapping,
        "warnings": report.warnings,
        "duplicates_rejected": dup_hard,
        "duplicates_flagged_for_review": dup_soft,
        "auto_matched_to_invoices": matched,
        "needs_review": sum(1 for p in preview if p.get("needs_review")),
    }
    return {
        "batch_id": batch.id, "dry_run": dry_run, "adapter": adapter_key,
        "filename": filename,
        "rows_seen": report.rows_seen, "rows_imported": batch.rows_imported,
        "rows_rejected": report.rows_rejected,
        "duplicates_rejected": dup_hard, "duplicates_flagged": dup_soft,
        "auto_matched": matched,
        "errors": report.errors[:50], "warnings": report.warnings,
        "detected_format": report.detected_format,
        "column_mapping": report.column_mapping,
        "preview": preview[:200],
        "note": ("Nothing was written - this is a preview." if dry_run else
                 "Imported. Rows flagged for review are visible on the Transactions screen."),
    }


def _build_invoice(db, business_id: str, row: dict, cache: dict) -> tuple[Invoice, str]:
    name = (row.get("counterparty") or "Unidentified party").strip() or "Unidentified party"
    key = party_key(name)
    cp = db.scalar(select(Counterparty).where(
        Counterparty.business_id == business_id, Counterparty.normalised_name == key))
    note = "matched existing counterparty"
    if cp is None:
        cp = Counterparty(
            id=_uid(), business_id=business_id, name=name, normalised_name=key,
            party_type=("customer" if row.get("kind") == "sales" else "supplier"),
            gstin=row.get("gstin"), credit_days=30)
        db.add(cp)
        db.flush()
        note = "created a new counterparty"
    total = int(row.get("total_paise") or 0)
    taxable = int(row.get("taxable_paise") or round(total / 1.18))
    tax = int(row.get("tax_paise") or (total - taxable))
    issue = row["issue_date"]
    inv = Invoice(
        id=_uid(), business_id=business_id, counterparty_id=cp.id,
        kind=InvoiceKind.SALES if row.get("kind") == "sales" else InvoiceKind.PURCHASE,
        invoice_no=str(row["invoice_no"])[:60], issue_date=issue,
        due_date=issue + __import__("datetime").timedelta(days=cp.credit_days),
        credit_days=cp.credit_days, taxable_paise=taxable, tax_paise=tax,
        total_paise=total, settled_paise=0, written_off_paise=0,
        status=InvoiceStatus.OPEN, source_system=row.get("source", "import"),
        evidence=Evidence.IMPORTED_ACTUAL, raw_json={k: str(v) for k, v in row.items()
                                                     if k != "__type"})
    return inv, note


def catalogue() -> dict:
    from app.integrations.base import PLANNED
    return {
        "available": [a.describe() for a in REGISTRY.values()
                      if a.status == "available"],
        "requires_setup": [a.describe() for a in REGISTRY.values()
                           if a.status != "available"],
        "planned": PLANNED,
        "principle": ("RUNWAY lists an integration as available only when it works with "
                      "no credentials beyond a file you already have. Everything else "
                      "states exactly what it would need - credentials, a partner, or "
                      "eligibility as a regulated entity."),
    }
