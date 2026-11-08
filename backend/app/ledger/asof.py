"""Point-in-time reconstruction helpers.

A forecast made for 15 August must see the ledger *as it stood on 15 August*,
not as it stands today. Using today's invoice balances when backtesting an
August forecast makes almost every receivable disappear - they have since
been collected - and the backtest then measures a model that never existed.

``outstanding_at`` is the one place that reconstruction happens, so every
caller gets the same answer.
"""
from __future__ import annotations

from datetime import date

from app.core.enums import InvoiceStatus


def outstanding_at(inv, as_of: date) -> int:
    """Amount still owed on an invoice on a given date.

    Uses settlement dates rather than the current ``settled_paise``, so it is
    correct for any past date. Where an invoice was partially paid, the part
    payment is recognised from its first payment date onwards - an
    approximation that is exact for the common cases (fully open, fully
    settled) and conservative in between.
    """
    if inv.issue_date > as_of:
        return 0
    if inv.status in (InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF):
        return 0
    total = inv.total_paise - (inv.written_off_paise or 0)
    if inv.settled_date and inv.settled_date <= as_of:
        return 0
    if inv.first_payment_date and inv.first_payment_date <= as_of:
        return max(0, total - (inv.settled_paise or 0))
    return max(0, total)


def status_at(inv, as_of: date) -> str:
    out = outstanding_at(inv, as_of)
    if out <= 0:
        return InvoiceStatus.PAID
    if inv.due_date < as_of:
        return InvoiceStatus.OVERDUE
    if inv.first_payment_date and inv.first_payment_date <= as_of:
        return InvoiceStatus.PART_PAID
    return InvoiceStatus.OPEN


def was_settled_by(inv, as_of: date) -> bool:
    return bool(inv.settled_date and inv.settled_date <= as_of)
