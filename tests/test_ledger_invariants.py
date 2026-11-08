"""Accounting invariants. If any of these fail, nothing else can be trusted."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import case, func, select

from app.analytics.cash import account_balance, cash_position
from app.core.enums import Direction, InvoiceKind, InvoiceStatus
from app.models import Account, Allocation, Invoice, Transaction

TODAY = date(2026, 11, 7)


def test_opening_plus_credits_minus_debits_equals_closing(db, business_id):
    accounts = db.scalars(select(Account).where(Account.business_id == business_id)).all()
    assert accounts
    for a in accounts:
        b = account_balance(db, a, TODAY)
        assert b.closing_paise == b.opening_paise + b.credits_paise - b.debits_paise, a.name


def test_no_allocation_exceeds_its_invoice(db, business_id):
    rows = db.execute(
        select(Allocation.invoice_id, func.sum(Allocation.amount_paise))
        .where(Allocation.business_id == business_id)
        .group_by(Allocation.invoice_id)).all()
    assert rows
    for invoice_id, allocated in rows:
        inv = db.get(Invoice, invoice_id)
        assert allocated <= inv.total_paise, (
            f"{inv.invoice_no}: allocated {allocated} exceeds total {inv.total_paise} - "
            f"reconciliation created money")


def test_no_allocation_exceeds_its_transaction(db, business_id):
    rows = db.execute(
        select(Allocation.transaction_id, func.sum(Allocation.amount_paise))
        .where(Allocation.business_id == business_id)
        .group_by(Allocation.transaction_id)).all()
    for txn_id, allocated in rows:
        t = db.get(Transaction, txn_id)
        # A gateway settlement credits the invoice with the GROSS while only the
        # net reached the bank, so the ceiling is gross where one exists.
        ceiling = t.gross_paise or t.amount_paise
        assert allocated <= ceiling, (
            f"transaction {t.id}: allocated {allocated} exceeds {ceiling}")


def test_settled_equals_sum_of_allocations(db, business_id):
    invoices = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.settled_paise > 0).limit(400)).all()
    assert invoices
    for inv in invoices:
        allocated = db.scalar(select(func.coalesce(func.sum(Allocation.amount_paise), 0))
                              .where(Allocation.invoice_id == inv.id)) or 0
        assert allocated == inv.settled_paise, inv.invoice_no


def test_outstanding_is_never_negative(db, business_id):
    for inv in db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all():
        assert inv.outstanding_paise >= 0, inv.invoice_no
        assert inv.settled_paise <= inv.total_paise, inv.invoice_no


def test_paid_invoices_have_a_settled_date(db, business_id):
    rows = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.status == InvoiceStatus.PAID)).all()
    assert rows
    for inv in rows:
        assert inv.settled_date is not None, inv.invoice_no
        assert inv.settled_date >= inv.issue_date, inv.invoice_no


def test_transaction_amounts_are_positive_with_a_direction(db, business_id):
    for t in db.scalars(select(Transaction).where(
            Transaction.business_id == business_id).limit(500)).all():
        assert t.amount_paise > 0
        assert t.direction in (Direction.CREDIT, Direction.DEBIT)
        assert t.signed_paise == (t.amount_paise if t.direction == Direction.CREDIT
                                  else -t.amount_paise)


def test_cash_position_decomposition(db, business_id):
    p = cash_position(db, business_id, TODAY)
    assert p.available_liquidity_paise == p.cash_paise - p.restricted_paise - p.committed_paise
    assert p.restricted_paise >= 0
    assert p.committed_paise >= 0
    # Overdraft headroom is credit, reported separately and never folded into cash.
    assert p.total_accessible_paise == p.available_liquidity_paise + p.overdraft_headroom_paise


def test_an_unpaid_invoice_is_never_counted_as_cash(db, business_id):
    p = cash_position(db, business_id, TODAY)
    ar = db.scalar(select(func.coalesce(func.sum(
        Invoice.total_paise - Invoice.settled_paise), 0)).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.status != InvoiceStatus.PAID)) or 0
    assert ar > 0, "the fixture should have open receivables for this test to mean anything"
    # Portable case(), not the SQLite-only IIF function: this suite also
    # runs against PostgreSQL via RUNWAY_TEST_DATABASE_URL.
    signed = case((Transaction.direction == Direction.CREDIT, Transaction.amount_paise),
                  else_=-Transaction.amount_paise)
    txn_net = db.scalar(
        select(func.coalesce(func.sum(signed), 0))
        .where(Transaction.business_id == business_id,
               Transaction.value_date <= TODAY)) or 0
    opening = db.scalar(select(func.coalesce(func.sum(Account.opening_balance_paise), 0))
                        .where(Account.business_id == business_id)) or 0
    assert p.cash_paise == opening + txn_net
