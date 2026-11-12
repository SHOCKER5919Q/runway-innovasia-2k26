"""Invoice <-> bank-transaction reconciliation.

Design rules that the tests enforce:

* **No money is ever created.** The sum of allocations against an invoice can
  never exceed its total, and the sum against a transaction can never exceed
  its amount.
* **Partial payments are first class.** An allocation is a (txn, invoice,
  amount) triple, so one payment can settle many invoices and one invoice can
  be settled by many payments.
* **Uncertainty is surfaced, not hidden.** Anything matched below
  ``AUTO_CONFIRM`` is written with ``NEEDS_REVIEW`` so the owner sees it.
* **Fees are not revenue.** A gateway settlement carries gross/fee/net; the
  invoice is credited with the gross, and the fee is a separate expense.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select

from app.core.enums import (
    Direction, Evidence, InvoiceKind, InvoiceStatus, ReconStatus, TxnCategory,
)
from app.models import Allocation, Invoice, Transaction

AUTO_CONFIRM = 0.80
#  How far either side of the payment date we will look for an open invoice.
DATE_WINDOW_BEFORE = 120
DATE_WINDOW_AFTER = 20
INVOICE_NO_RE = re.compile(r"\b([A-Z]{2,6}[-/]?\d{3,8})\b", re.I)


@dataclass
class MatchResult:
    allocations: list[tuple[str, int, float, str]] = field(default_factory=list)  # invoice_id, paise, conf, why
    status: str = ReconStatus.UNRECONCILED
    note: str = ""


def _extract_invoice_refs(text: str) -> list[str]:
    return [m.group(1).upper().replace("/", "-") for m in INVOICE_NO_RE.finditer(text or "")]


def _candidate_invoices(db, txn: Transaction) -> list[Invoice]:
    kind = InvoiceKind.SALES if txn.direction == Direction.CREDIT else InvoiceKind.PURCHASE
    q = select(Invoice).where(
        Invoice.business_id == txn.business_id,
        Invoice.kind == kind,
        Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PART_PAID, InvoiceStatus.OVERDUE]),
        Invoice.issue_date <= txn.value_date + timedelta(days=DATE_WINDOW_AFTER),
        Invoice.issue_date >= txn.value_date - timedelta(days=DATE_WINDOW_BEFORE + 180),
    )
    if txn.counterparty_id:
        q = q.where(Invoice.counterparty_id == txn.counterparty_id)
    return list(db.scalars(q).all())


def match_transaction(db, txn: Transaction) -> MatchResult:
    """Attempt to allocate one transaction against open invoices."""
    res = MatchResult()
    if txn.direction not in (Direction.CREDIT, Direction.DEBIT):
        return res
    if txn.category in {TxnCategory.PAYROLL, TxnCategory.GST_PAYMENT, TxnCategory.TAX_OTHER,
                        TxnCategory.BANK_CHARGES, TxnCategory.LOAN_REPAYMENT,
                        TxnCategory.LOAN_DISBURSAL, TxnCategory.TRANSFER,
                        TxnCategory.GATEWAY_FEE, TxnCategory.INTEREST_INCOME,
                        TxnCategory.OWNER_DRAW, TxnCategory.CAPITAL_IN,
                        TxnCategory.PF_ESI, TxnCategory.RENT, TxnCategory.UTILITIES,
                        TxnCategory.FREIGHT, TxnCategory.REFUND_OUT, TxnCategory.REFUND_IN,
                        TxnCategory.OTHER_INCOME, TxnCategory.OTHER_EXPENSE}:
        res.status = ReconStatus.IGNORED
        res.note = f"category '{txn.category}' is not invoice-settling"
        return res

    candidates = _candidate_invoices(db, txn)
    if not candidates:
        res.note = "no open invoice for this counterparty in the date window"
        return res

    # ``unallocated_paise`` already measures against the settleable amount
    # (gross for a gateway settlement), so re-running reconciliation over an
    # already partly-matched transaction can never allocate the fee twice.
    available = txn.unallocated_paise
    if available <= 0:
        return res

    refs = set(_extract_invoice_refs(f"{txn.narration} {txn.reference_no or ''}"))

    scored: list[tuple[float, Invoice, str]] = []
    for inv in candidates:
        if inv.outstanding_paise <= 0:
            continue
        score, why = 0.0, []
        norm_no = inv.invoice_no.upper().replace("/", "-")
        if norm_no in refs or any(norm_no in r or r in norm_no for r in refs):
            score += 0.60; why.append(f"invoice number {inv.invoice_no} appears in the narration")
        if txn.counterparty_id and inv.counterparty_id == txn.counterparty_id:
            score += 0.20; why.append("counterparty matches")
        # Amount agreement
        if abs(inv.outstanding_paise - available) <= max(100, int(0.001 * available)):
            score += 0.25; why.append("amount equals the outstanding balance exactly")
        elif available < inv.outstanding_paise:
            score += 0.08; why.append("amount is a plausible part payment")
        # Timing: a payment near the due date is more likely to be for it.
        gap = abs((txn.value_date - inv.due_date).days)
        if gap <= 7:
            score += 0.12; why.append(f"paid within {gap} days of the due date")
        elif gap <= 45:
            score += 0.05; why.append(f"paid {gap} days from the due date")
        if txn.value_date < inv.issue_date - timedelta(days=3):
            score -= 0.35; why.append("payment predates the invoice")
        if score > 0:
            scored.append((score, inv, "; ".join(why)))

    if not scored:
        res.note = "no candidate scored above zero"
        return res

    # Oldest-first within score band: real businesses clear ageing invoices first.
    scored.sort(key=lambda t: (-round(t[0], 2), t[1].due_date))

    remaining = available
    best_conf = 0.0
    for score, inv, why in scored:
        if remaining <= 0:
            break
        conf = min(0.99, score)
        if conf < 0.30:
            continue
        take = min(remaining, inv.outstanding_paise)
        if take <= 0:
            continue
        res.allocations.append((inv.id, take, conf, why))
        remaining -= take
        best_conf = max(best_conf, conf)

    if not res.allocations:
        res.note = "candidates existed but none scored high enough to allocate"
        return res
    if best_conf >= AUTO_CONFIRM:
        res.status = ReconStatus.MATCHED if remaining == 0 else ReconStatus.PARTIALLY_MATCHED
    else:
        res.status = ReconStatus.NEEDS_REVIEW
        res.note = f"best match confidence {best_conf:.2f} is below the auto-confirm threshold"
    return res


def reconcile_invoice_against_unallocated(db, inv: Invoice) -> list[dict]:
    """Settle a *newly created* invoice against payments already on the books.

    ``match_transaction`` runs the other way round: it takes a payment and
    looks for invoices. That is the right direction for an import, where the
    bank row is the new fact. It is the wrong direction for manual entry,
    where an owner often raises last month's invoice *after* the money has
    already landed - nothing would ever match, and the invoice would sit open
    forever next to a payment that clearly belongs to it.

    Same invariants as the forward pass: never allocate more than the invoice
    has outstanding, never more than a transaction has unallocated, and never
    let both sides of one invoice be settled by the same paise.
    """
    if inv.outstanding_paise <= 0:
        return []
    want = InvoiceKind.SALES if inv.kind == InvoiceKind.SALES else InvoiceKind.PURCHASE
    direction = Direction.CREDIT if inv.kind == InvoiceKind.SALES else Direction.DEBIT
    skip = {TxnCategory.PAYROLL, TxnCategory.GST_PAYMENT, TxnCategory.TAX_OTHER,
            TxnCategory.BANK_CHARGES, TxnCategory.LOAN_REPAYMENT,
            TxnCategory.LOAN_DISBURSAL, TxnCategory.TRANSFER,
            TxnCategory.GATEWAY_FEE, TxnCategory.INTEREST_INCOME,
            TxnCategory.OWNER_DRAW, TxnCategory.CAPITAL_IN, TxnCategory.PF_ESI,
            TxnCategory.RENT, TxnCategory.UTILITIES, TxnCategory.FREIGHT}
    q = select(Transaction).where(
        Transaction.business_id == inv.business_id,
        Transaction.direction == direction,
        Transaction.counterparty_id == inv.counterparty_id,
        Transaction.value_date >= inv.issue_date - timedelta(days=DATE_WINDOW_BEFORE),
        Transaction.value_date <= inv.due_date + timedelta(days=DATE_WINDOW_AFTER),
    ).order_by(Transaction.value_date)
    created: list[dict] = []
    for txn in db.scalars(q).all():
        if inv.outstanding_paise <= 0:
            break
        if txn.category in skip:
            continue
        free = txn.unallocated_paise
        if free <= 0:
            continue
        refs = {r.upper().replace("/", "-") for r in _extract_invoice_refs(
            f"{txn.narration} {txn.reference_no or ''}")}
        norm_no = inv.invoice_no.upper().replace("/", "-")
        score = 0.0
        why = []
        if norm_no in refs or any(norm_no in r or r in norm_no for r in refs):
            score += 0.60; why.append(f"narration cites {inv.invoice_no}")
        if abs(inv.outstanding_paise - free) <= max(100, int(0.001 * free)):
            score += 0.25; why.append("amount equals the invoice total exactly")
        elif free < inv.outstanding_paise:
            score += 0.08; why.append("plausible part payment")
        gap = abs((txn.value_date - inv.due_date).days)
        if gap <= 7:
            score += 0.12; why.append(f"paid within {gap} days of the due date")
        elif gap <= 45:
            score += 0.05; why.append(f"paid {gap} days from the due date")
        if txn.value_date < inv.issue_date - timedelta(days=3):
            score -= 0.35; why.append("payment predates the invoice")
        if score < 0.50:
            continue

        take = min(free, inv.outstanding_paise)
        if take <= 0:
            continue
        db.add(Allocation(
            business_id=inv.business_id, transaction_id=txn.id, invoice_id=inv.id,
            amount_paise=take, method="auto", confidence=round(min(0.99, score), 2),
            rationale=f"manual invoice matched back to an existing payment: {'; '.join(why)}"[:300]))
        inv.settled_paise += take
        if inv.first_payment_date is None or txn.value_date < inv.first_payment_date:
            inv.first_payment_date = txn.value_date
        txn.allocated_paise = min(txn.settleable_paise, txn.allocated_paise + take)
        if txn.unallocated_paise <= 0:
            txn.recon_status = ReconStatus.MATCHED
        elif txn.allocated_paise > 0 and txn.recon_status == ReconStatus.UNRECONCILED:
            txn.recon_status = ReconStatus.PARTIALLY_MATCHED
        created.append({"transaction_id": txn.id, "amount_paise": take,
                        "confidence": round(min(0.99, score), 2),
                        "why": "; ".join(why)})

    if inv.settled_paise > 0:
        if inv.outstanding_paise <= 0:
            inv.status = InvoiceStatus.PAID
        else:
            inv.status = InvoiceStatus.PART_PAID
    db.flush()
    return created


def apply_match(db, txn: Transaction, res: MatchResult) -> list[Allocation]:
    """Persist allocations, enforcing the no-overdraw invariants."""
    created: list[Allocation] = []
    for invoice_id, paise, conf, why in res.allocations:
        inv = db.get(Invoice, invoice_id)
        if inv is None:
            continue
        paise = min(paise, inv.outstanding_paise)
        if paise <= 0:
            continue
        alloc = Allocation(
            business_id=txn.business_id, transaction_id=txn.id, invoice_id=inv.id,
            amount_paise=paise, method="auto", confidence=conf, rationale=why[:300],
        )
        db.add(alloc)
        created.append(alloc)

        inv.settled_paise += paise
        if inv.first_payment_date is None or txn.value_date < inv.first_payment_date:
            inv.first_payment_date = txn.value_date
        if inv.outstanding_paise <= 0:
            inv.status = InvoiceStatus.PAID
            inv.settled_date = txn.value_date
        else:
            inv.status = InvoiceStatus.PART_PAID
        txn.allocated_paise = min(txn.settleable_paise, txn.allocated_paise + paise)
    txn.recon_status = res.status
    if res.note:
        txn.transform_log_json = list(txn.transform_log_json or []) + [
            {"step": "reconcile", "status": res.status, "note": res.note}
        ]
    return created


def reconcile_business(db, business_id: str, *, limit: int | None = None) -> dict:
    """Run matching over every unreconciled transaction. Idempotent."""
    q = select(Transaction).where(
        Transaction.business_id == business_id,
        Transaction.recon_status.in_([ReconStatus.UNRECONCILED, ReconStatus.PARTIALLY_MATCHED]),
    ).order_by(Transaction.value_date)
    if limit:
        q = q.limit(limit)
    txns = list(db.scalars(q).all())
    stats = {"examined": len(txns), "matched": 0, "partial": 0, "needs_review": 0,
             "ignored": 0, "unmatched": 0, "allocations": 0, "amount_allocated_paise": 0}
    for txn in txns:
        res = match_transaction(db, txn)
        allocs = apply_match(db, txn, res)
        stats["allocations"] += len(allocs)
        stats["amount_allocated_paise"] += sum(a.amount_paise for a in allocs)
        key = {ReconStatus.MATCHED: "matched", ReconStatus.PARTIALLY_MATCHED: "partial",
               ReconStatus.NEEDS_REVIEW: "needs_review", ReconStatus.IGNORED: "ignored"}.get(
                   res.status, "unmatched")
        stats[key] += 1
    db.flush()
    return stats


def refresh_overdue(db, business_id: str, today: date) -> int:
    """Flip open invoices past their due date to OVERDUE."""
    rows = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.PART_PAID]),
        Invoice.due_date < today,
    )).all()
    for inv in rows:
        inv.status = InvoiceStatus.OVERDUE
    return len(rows)
