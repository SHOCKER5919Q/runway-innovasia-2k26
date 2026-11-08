"""Reconciliation behaviour: duplicates, partial payments, refunds, fees."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.enums import Direction, Evidence, InvoiceKind, InvoiceStatus, ReconStatus
from app.ledger.classifier import classify
from app.ledger.entities import resolve_counterparty
from app.ledger.normalise import detect_duplicate, fingerprint, narration_tokens, party_key
from app.ledger.reconciliation import apply_match, match_transaction
from app.models import Account, Counterparty, Invoice, Transaction, _uid

TODAY = date(2026, 11, 7)


def _txn(db, business_id, account_id, **kw):
    d = dict(value_date=TODAY, amount_paise=1_00_000_00, direction=Direction.CREDIT,
             narration="NEFT CR-TEST", reference_no=None)
    d.update(kw)
    t = Transaction(id=_uid(), business_id=business_id, account_id=account_id,
                    allocated_paise=0, evidence=Evidence.IMPORTED_ACTUAL,
                    recon_status=ReconStatus.UNRECONCILED, **d)
    t.fingerprint = fingerprint(business_id=business_id, account_id=account_id,
                                value_date=d["value_date"], amount_paise=d["amount_paise"],
                                direction=d["direction"], reference_no=d["reference_no"],
                                narration=d["narration"])
    return t


@pytest.fixture()
def account(db, business_id):
    return db.scalars(select(Account).where(Account.business_id == business_id)).first()


# ── duplicates ────────────────────────────────────────────────────

def test_identical_reference_is_a_hard_duplicate(db, business_id, account):
    a = _txn(db, business_id, account.id, reference_no="NEFT-UNIQ-001",
             narration="NEFT CR-ABC DISTRIBUTORS-INV-9001")
    db.add(a); db.flush()
    b = _txn(db, business_id, account.id, reference_no="NEFT-UNIQ-001",
             narration="NEFT CR-ABC DISTRIBUTORS-INV-9001")
    is_dup, existing, reason = detect_duplicate(db, business_id, b)
    assert is_dup is True
    assert existing == a.id
    assert "reference" in reason
    db.rollback()


def test_same_amount_without_reference_is_only_suspected(db, business_id, account):
    """A business genuinely can pay the same supplier the same amount twice.
    RUNWAY flags it; it must never delete it."""
    a = _txn(db, business_id, account.id, reference_no=None,
             direction=Direction.DEBIT, narration="NEFT DR-XYZ FOODS BILL SETTLEMENT")
    db.add(a); db.flush()
    b = _txn(db, business_id, account.id, reference_no=None,
             value_date=TODAY + timedelta(days=1),
             direction=Direction.DEBIT, narration="NEFT DR-XYZ FOODS BILL SETTLEMENT")
    is_dup, existing, reason = detect_duplicate(db, business_id, b)
    assert is_dup is False, "must not hard-reject without a shared bank reference"
    assert existing == a.id
    db.rollback()


def test_different_references_same_amount_are_two_real_payments(db, business_id, account):
    a = _txn(db, business_id, account.id, reference_no="NEFT-A-1",
             direction=Direction.DEBIT, narration="NEFT DR-SUPPLIER ONE")
    db.add(a); db.flush()
    b = _txn(db, business_id, account.id, reference_no="NEFT-B-2",
             direction=Direction.DEBIT, narration="NEFT DR-SUPPLIER TWO")
    is_dup, existing, _ = detect_duplicate(db, business_id, b)
    assert is_dup is False and existing is None
    db.rollback()


# ── classification ────────────────────────────────────────────────

@pytest.mark.parametrize("narration,direction,expected", [
    ("GST CHALLAN PMT-06 GSTR-3B OCT 2026", "debit", "gst_payment"),
    ("SALARY PAYOUT NOV 2026 STAFF 14 NOS", "debit", "payroll"),
    ("EMI TERM LOAN HDFC AC 4417", "debit", "loan_repayment"),
    ("RENT GODOWN+OFFICE NOV", "debit", "rent"),
    ("TDS CHALLAN ITNS-281 194C", "debit", "tax_other"),
    ("ELECTRICITY TGSPDCL BILL", "debit", "utilities"),
    ("BANK CHARGES NEFT + SMS ALERT", "debit", "bank_charges"),
])
def test_rules_classify_indian_narrations(narration, direction, expected):
    cat, conf, rule = classify(narration, direction)
    assert cat == expected, f"{narration} -> {cat} ({rule})"
    assert conf > 0.5


def test_a_known_counterparty_lifts_a_generic_narration_above_review():
    """A bare transport keyword is weak evidence on its own. Matching it to a
    known customer is what makes it confident."""
    bare = classify("NEFT CR-ABC DISTRIBUTORS-INV-1807", "credit")
    assert bare[1] < 0.55, "a generic inbound transfer alone must stay reviewable"
    withcp = classify("NEFT CR-ABC DISTRIBUTORS-INV-1807", "credit",
                      counterparty_type="customer")
    assert withcp[0] == "customer_receipt"
    assert withcp[1] > 0.6


def test_a_matched_invoice_overrides_the_narration():
    """Hard evidence beats a keyword. A receipt matched to a sales invoice is
    a customer receipt whatever the bank wrote."""
    cat, conf, rule = classify("MISC CREDIT ENTRY", "credit", matched_invoice_kind="sales")
    assert cat == "customer_receipt"
    assert conf >= 0.99


def test_unmatched_narration_is_low_confidence_not_a_guess():
    cat, conf, rule = classify("UPI/P2A/418822190034/PAYMENT", "credit")
    assert conf < 0.55, "an unidentifiable credit must be surfaced, not confidently labelled"


# ── entity resolution ─────────────────────────────────────────────

def test_counterparty_resolution_matches_on_name(db, business_id):
    cp_id, conf, why = resolve_counterparty(
        db, business_id, "NEFT CR-ABC DISTRIBUTORS-INV-1807", Direction.CREDIT)
    assert cp_id is not None
    cp = db.get(Counterparty, cp_id)
    assert "ABC" in cp.name.upper()
    assert conf > 0.5


def test_counterparty_resolution_declines_when_there_is_no_signal(db, business_id):
    cp_id, conf, why = resolve_counterparty(
        db, business_id, "UPI/P2A/999999999999/PAYMENT", Direction.CREDIT)
    assert cp_id is None, "RUNWAY must not guess a counterparty from a bare UPI reference"


def test_party_key_strips_legal_suffixes():
    assert party_key("ABC Distributors Pvt. Ltd.") == party_key("ABC DISTRIBUTORS")


def test_narration_tokens_drop_transport_noise():
    toks = narration_tokens("NEFT CR-HDFC0001-ABC DISTRIBUTORS PVT LTD-993881772")
    assert "neft" not in toks and "993881772" not in toks
    assert "abc" in toks and "distributors" in toks


# ── matching ──────────────────────────────────────────────────────

def test_partial_payment_leaves_the_invoice_open(db, business_id, account):
    inv = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.OVERDUE]),
        Invoice.settled_paise == 0).limit(1)).first()
    assert inv is not None
    half = inv.total_paise // 2
    cp = db.get(Counterparty, inv.counterparty_id)
    t = _txn(db, business_id, account.id, amount_paise=half,
             narration=f"NEFT CR-{cp.name.upper()}-{inv.invoice_no}",
             reference_no="NEFT-PART-1", counterparty_id=inv.counterparty_id)
    db.add(t); db.flush()
    res = match_transaction(db, t)
    apply_match(db, t, res)
    db.flush()
    assert inv.settled_paise == half
    assert inv.outstanding_paise == inv.total_paise - half
    assert inv.status == InvoiceStatus.PART_PAID
    db.rollback()


def test_payment_predating_the_invoice_is_penalised(db, business_id, account):
    inv = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.settled_paise == 0).limit(1)).first()
    cp = db.get(Counterparty, inv.counterparty_id)
    t = _txn(db, business_id, account.id, amount_paise=inv.total_paise,
             value_date=inv.issue_date - timedelta(days=30),
             narration=f"NEFT CR-{cp.name.upper()}-{inv.invoice_no}",
             counterparty_id=inv.counterparty_id, reference_no="NEFT-EARLY")
    db.add(t); db.flush()
    res = match_transaction(db, t)
    confidences = [c for _, _, c, _ in res.allocations]
    assert not confidences or max(confidences) < 0.8
    db.rollback()


def test_non_invoice_categories_are_marked_ignored_not_unmatched(db, business_id, account):
    t = _txn(db, business_id, account.id, direction=Direction.DEBIT,
             narration="SALARY PAYOUT NOV 2026", category="payroll")
    db.add(t); db.flush()
    res = match_transaction(db, t)
    assert res.status == ReconStatus.IGNORED
    db.rollback()


def test_reconciliation_is_idempotent(db, business_id, account):
    """Running the matcher twice must not allocate twice."""
    inv = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.settled_paise == 0).limit(1)).first()
    cp = db.get(Counterparty, inv.counterparty_id)
    t = _txn(db, business_id, account.id, amount_paise=inv.total_paise // 3,
             narration=f"NEFT CR-{cp.name.upper()}-{inv.invoice_no}",
             counterparty_id=inv.counterparty_id, reference_no="NEFT-IDEM")
    db.add(t); db.flush()
    apply_match(db, t, match_transaction(db, t))
    db.flush()
    first = inv.settled_paise
    apply_match(db, t, match_transaction(db, t))
    db.flush()
    assert inv.settled_paise == first, "a second pass must not re-allocate the same money"
    db.rollback()


def test_gateway_settlement_credits_gross_not_net(db, business_id):
    """The invoice must clear in full even though only the net hit the bank."""
    t = db.scalars(select(Transaction).where(
        Transaction.business_id == business_id,
        Transaction.gross_paise.isnot(None)).limit(1)).first()
    assert t is not None, "the fixture should contain gateway settlements"
    assert t.gross_paise == t.amount_paise + t.fee_paise
    assert t.settleable_paise == t.gross_paise
    assert t.allocated_paise <= t.gross_paise
