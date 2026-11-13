"""Import pipeline: parse -> dedupe -> resolve -> classify -> reconcile."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.core.enums import Direction, Evidence, InvoiceKind, InvoiceStatus, ReconStatus, TxnCategory
from app.integrations import adapters as _adapters  # noqa: F401 (registers adapters)
from app.integrations import pdf_invoice as _pdf_invoice  # noqa: F401
from app.integrations.base import REGISTRY, NormalisedRow
from app.ledger.classifier import classify
from app.ledger.entities import resolve_counterparty
from app.ledger.normalise import detect_duplicate, fingerprint, mark_suspected_duplicate, party_key
from app.ledger.reconciliation import (
    KEYWORD_GUESSED, apply_match, match_transaction, reconcile_business, refresh_overdue,
)
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
    # Wrong importer picked? Rather than read 0 rows, try the others that
    # accept this kind of file and use the first that reads something,
    # saying so. (A sales register sent to "Bank statement" used to show 0.)
    if not parsed:
        low = (filename or "").lower()
        order = (["pdf_invoice"] if low.endswith(".pdf") else
                 ["tally_xml"] if low.endswith(".xml") else
                 ["gst_invoice_json", "bank_csv"] if low.endswith(".json") else
                 ["bank_csv"] if low.endswith((".xlsx", ".xlsm")) else
                 ["gst_invoice_json", "upi_settlement_csv", "bank_csv", "tally_xml"])
        for key in order:
            if key == adapter_key or key not in REGISTRY:
                continue
            try:
                p2, r2 = REGISTRY[key].parse(content, filename=filename)
            except Exception:
                continue
            if p2:
                label = REGISTRY[key].label
                parsed, report, adapter_key = p2, r2, key
                report.warnings.insert(0, f"Read with the '{label}' importer - the one "
                                          f"selected could not read this file.")
                break
    batch = ImportBatch(id=_uid(), business_id=business_id, adapter=adapter_key,
                        filename=filename, status="parsed",
                        rows_seen=report.rows_seen, rows_rejected=report.rows_rejected,
                        errors_json=_json_safe(report.errors[:100]))

    created_txn, created_inv, dup_hard, dup_soft = [], [], 0, 0
    preview: list[dict] = []
    cache: dict = {}
    # A file can repeat a row within itself. Checking only against the
    # database would let an in-file duplicate through on a dry run, where
    # nothing has been flushed yet.
    seen_in_batch: dict[str, int] = {}
    out_of_range = 0
    seen_invoices: set[tuple[str, str]] = set()

    for item in parsed:
        if isinstance(item, NormalisedRow):
            row, kind = item, "transaction"
        elif isinstance(item, dict) and item.get("__type") == "transaction":
            row, kind = item["row"], "transaction"
        elif isinstance(item, dict) and item.get("__type") == "invoice":
            row, kind = item, "invoice"
        else:
            continue

        if kind == "transaction":
            # Guard: a statement row must fall inside this account's life.
            # A file for another business or another era (e.g. a 2010 export
            # loaded into an account opened in 2025) would otherwise be booked
            # in full and rewrite every figure. Such rows are refused with a
            # reason instead.
            why = None
            if account.opening_date and row.value_date < account.opening_date:
                why = (f"dated {row.value_date.isoformat()}, before this account was opened "
                       f"({account.opening_date.isoformat()}) - is this the right account "
                       f"or business?")
            elif today and row.value_date > today + timedelta(days=1):
                why = (f"dated {row.value_date.isoformat()}, after the as-of date "
                       f"{today.isoformat()}")
            if why:
                report.rows_rejected += 1
                out_of_range += 1
                if len(report.errors) < 100:
                    report.errors.append({"row": None, "date": row.value_date.isoformat(), "error": why})
                continue

        if kind == "invoice":
            inv_kind = InvoiceKind.SALES if row.get("kind") == "sales" else InvoiceKind.PURCHASE
            inv_no = str(row["invoice_no"])[:60]
            dup_inv_key = (inv_kind, inv_no)
            existing_inv = db.scalar(select(Invoice).where(
                Invoice.business_id == business_id,
                Invoice.kind == inv_kind,
                Invoice.invoice_no == inv_no,
            ))
            if existing_inv or dup_inv_key in seen_invoices:
                dup_hard += 1
                preview.append({
                    "kind": "duplicate_rejected",
                    "date": row["issue_date"].isoformat(),
                    "invoice_no": inv_no,
                    "counterparty": row.get("counterparty"),
                    "amount_paise": int(row.get("total_paise") or 0),
                    "reason": f"{inv_kind} invoice {inv_no} already exists",
                })
                continue
            seen_invoices.add(dup_inv_key)
            inv, note = _build_invoice(db, business_id, row, cache)
            preview.append({
                "kind": "invoice", "invoice_no": inv.invoice_no,
                "date": inv.issue_date.isoformat(),
                "counterparty": row.get("counterparty"),
                "category": inv.kind,
                "amount_paise": inv.total_paise, "reason": note, "note": note,
            })
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

        cp_id, cp_conf, cp_why = None, 0.0, "no counterparty master data"
        if row.counterparty_hint:
            parties = cache.get(business_id)
            if parties is None:
                parties = list(db.scalars(select(Counterparty).where(Counterparty.business_id == business_id)).all())
                cache[business_id] = parties
            hint_key = party_key(row.counterparty_hint)
            exact_cp = next((p for p in parties if p.normalised_name == hint_key), None)
            if exact_cp is not None:
                cp_id, cp_conf, cp_why = exact_cp.id, 1.0, f"exact counterparty column match '{exact_cp.name}'"
        if cp_id is None:
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
        if created_inv:
            # If payments were imported before invoices, link unresolved counterparties and reconcile them now.
            party_cache: dict = {}
            unresolved_txns = db.scalars(
                select(Transaction).where(
                    Transaction.business_id == business_id,
                    Transaction.counterparty_id.is_(None),
                )
            ).all()
            if unresolved_txns:
                parties = list(db.scalars(select(Counterparty).where(Counterparty.business_id == business_id)).all())
                by_key = {p.normalised_name: p for p in parties}
                party_cache[business_id] = parties
                for ut in unresolved_txns:
                    hint = ""
                    if isinstance(ut.raw_json, dict):
                        hint = str(
                            ut.raw_json.get("Customer_Name") or ut.raw_json.get("customer_name")
                            or ut.raw_json.get("Supplier_Name") or ut.raw_json.get("supplier_name")
                            or ut.raw_json.get("party") or ut.raw_json.get("Party") or ""
                        ).strip()
                    exact_cp = by_key.get(party_key(hint)) if hint else None
                    if exact_cp is not None:
                        ut.counterparty_id = exact_cp.id
                        cp_type = exact_cp.party_type
                    else:
                        cp_id_resolved, _, _ = resolve_counterparty(
                            db, business_id, f"{ut.narration} {hint}".strip(), ut.direction, cache=party_cache)
                        if cp_id_resolved is None:
                            continue
                        ut.counterparty_id = cp_id_resolved
                        cp_obj = db.get(Counterparty, cp_id_resolved)
                        cp_type = cp_obj.party_type if cp_obj else None
                    cat, conf, rule = classify(ut.narration, ut.direction, counterparty_type=cp_type)
                    ut.category, ut.category_confidence, ut.category_source = cat, conf, rule
                    if ut.recon_status == ReconStatus.IGNORED:
                        ut.recon_status = ReconStatus.UNRECONCILED
                db.flush()

        for txn in created_txn:
            res = match_transaction(db, txn)
            apply_match(db, txn, res)
            if res.status in (ReconStatus.MATCHED, ReconStatus.PARTIALLY_MATCHED):
                matched += 1
                if txn.category in KEYWORD_GUESSED:
                    # Settling a trade invoice is the stronger evidence.
                    before = txn.category
                    txn.category = (TxnCategory.SUPPLIER_PAYMENT
                                    if txn.direction == Direction.DEBIT
                                    else TxnCategory.CUSTOMER_RECEIPT)
                    txn.category_source = f"settles a cited invoice (was {before})"
                    txn.category_confidence = max(txn.category_confidence or 0, 0.9)
        if created_inv and not created_txn:
            rstats = reconcile_business(db, business_id)
            matched += int(rstats.get("matched", 0)) + int(rstats.get("partial", 0))
        refresh_overdue(db, business_id, today or date.today())
        db.add(batch)
        db.flush()

    if out_of_range:
        report.warnings.append(
            f"{out_of_range} rows were refused because their dates fall outside this "
            f"account's life. Nothing from those rows was written.")
        batch.rows_rejected = report.rows_rejected
        batch.errors_json = _json_safe(report.errors[:100])
    batch.report_json = _json_safe({
        "invoice_ids": [i.id for i in created_inv],
        "detected_format": report.detected_format,
        "column_mapping": report.column_mapping,
        "warnings": report.warnings,
        "duplicates_rejected": dup_hard,
        "duplicates_flagged_for_review": dup_soft,
        "auto_matched_to_invoices": matched,
        "needs_review": sum(1 for p in preview if p.get("needs_review")),
    })
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
    from datetime import timedelta
    name = (row.get("counterparty") or "Unidentified party").strip() or "Unidentified party"
    key = party_key(name)
    cp = db.scalar(select(Counterparty).where(
        Counterparty.business_id == business_id, Counterparty.normalised_name == key))
    note = "matched existing counterparty"
    if cp is None:
        cp = Counterparty(
            id=_uid(), business_id=business_id, name=name, normalised_name=key,
            party_type=("customer" if row.get("kind") == "sales" else "supplier"),
            gstin=row.get("gstin"),
            msme_class=row.get("msme_class"),
            credit_days=int(row.get("credit_days") or 30))
        db.add(cp)
        db.flush()
        note = "created a new counterparty"
    elif row.get("msme_class") and not cp.msme_class:
        cp.msme_class = row.get("msme_class")
    total = int(row.get("total_paise") or 0)
    tax = row.get("tax_paise")
    if tax is not None:
        tax = int(tax)
        taxable = int(row.get("taxable_paise") if row.get("taxable_paise") is not None else (total - tax))
    else:
        taxable = int(row.get("taxable_paise") if row.get("taxable_paise") is not None else round(total / 1.18))
        tax = total - taxable
    issue = row["issue_date"]
    credit_days = int(row.get("credit_days") if row.get("credit_days") is not None else cp.credit_days)
    due = row.get("due_date") or (issue + timedelta(days=credit_days))
    settled = min(total, max(0, int(row.get("settled_paise") or 0)))
    settled_date = row.get("settled_date")
    if settled >= total:
        status = InvoiceStatus.PAID
        settled_date = settled_date or due
    elif settled > 0:
        status = InvoiceStatus.PART_PAID
    else:
        status = InvoiceStatus.OPEN
    inv = Invoice(
        id=_uid(), business_id=business_id, counterparty_id=cp.id,
        kind=InvoiceKind.SALES if row.get("kind") == "sales" else InvoiceKind.PURCHASE,
        invoice_no=str(row["invoice_no"])[:60], issue_date=issue,
        due_date=due, credit_days=credit_days,
        taxable_paise=taxable, tax_paise=tax, total_paise=total,
        settled_paise=settled, written_off_paise=0,
        status=status, settled_date=settled_date,
        source_system=row.get("source", "import"),
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


def _json_safe(v):
    """Dates and other non-JSON values in an adapter's report, as ISO strings.

    The PDF extractor reports each field with its parsed value, and a
    ``date`` in a JSON column made every committed PDF import fail with a
    500 (dry runs passed because they roll back before serialising).
    """
    from datetime import date as _date, datetime as _datetime
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, (_date, _datetime)):
        return v.isoformat()
    return v



def revert_batch(db, batch) -> dict:
    """Take one upload back out of the ledger.

    The batch record itself stays in import history, marked ``reverted``, so
    the audit trail still shows the file was loaded and then withdrawn.
    Settlements its payments made are reversed, so invoices it paid are open
    again; invoices it created are removed.
    """
    from app.models import Allocation
    txns = db.scalars(select(Transaction).where(Transaction.import_batch_id == batch.id)).all()
    reopened = set()
    for t in txns:
        for a in db.scalars(select(Allocation).where(Allocation.transaction_id == t.id)).all():
            inv = db.get(Invoice, a.invoice_id)
            if inv is not None:
                inv.settled_paise = max(0, (inv.settled_paise or 0) - a.amount_paise)
                if inv.settled_paise <= 0:
                    inv.first_payment_date = None
                    inv.settled_date = None
                    inv.status = InvoiceStatus.OPEN
                else:
                    inv.settled_date = None
                    inv.status = InvoiceStatus.PART_PAID
                reopened.add(inv.invoice_no)
            db.delete(a)
        db.delete(t)
    removed_inv = 0
    for inv_id in (batch.report_json or {}).get("invoice_ids", []):
        inv = db.get(Invoice, inv_id)
        if inv is not None and inv.business_id == batch.business_id:
            for a in db.scalars(select(Allocation).where(Allocation.invoice_id == inv.id)).all():
                t = db.get(Transaction, a.transaction_id)
                if t is not None:
                    t.allocated_paise = max(0, (t.allocated_paise or 0) - a.amount_paise)
                    if t.allocated_paise <= 0:
                        t.recon_status = ReconStatus.UNRECONCILED
                db.delete(a)
            db.delete(inv)
            removed_inv += 1
    batch.status = "reverted"
    batch.report_json = {**(batch.report_json or {}),
                         "reverted": {"transactions_removed": len(txns),
                                      "invoices_removed": removed_inv,
                                      "invoices_reopened": sorted(reopened)}}
    return batch.report_json["reverted"]
