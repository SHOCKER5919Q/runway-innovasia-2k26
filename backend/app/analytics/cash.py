"""Cash position from the ledger.

The distinction this module exists to enforce:

    cash in hand          what the bank statements actually say
  - restricted            lien-marked / pledged, cannot fund operations
  - committed             reserved against obligations due inside the
                          commitment horizon that the owner has asked us to
                          ring-fence (GST, payroll)
  = available liquidity   what is genuinely spendable today
  + overdraft headroom    borrowing capacity - reported separately because
                          it is credit, not cash

An unpaid invoice never appears in any of these figures.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta

from sqlalchemy import func, select

from app.core.enums import Direction, Evidence, InvoiceKind, InvoiceStatus
from app.models import Account, Invoice, Loan, Obligation, Transaction

COMMITMENT_HORIZON_DAYS = 30


@dataclass
class AccountBalance:
    account_id: str
    name: str
    kind: str
    masked_number: str | None
    opening_paise: int
    credits_paise: int
    debits_paise: int
    closing_paise: int
    restricted_paise: int
    overdraft_limit_paise: int
    last_transaction_date: str | None
    evidence: str


@dataclass
class CashPosition:
    as_of: str
    cash_paise: int
    restricted_paise: int
    committed_paise: int
    available_liquidity_paise: int
    overdraft_headroom_paise: int
    total_accessible_paise: int
    accounts: list[dict]
    committed_breakdown: list[dict]
    verified_share: float

    def dict(self) -> dict:
        return asdict(self)


def account_balance(db, account: Account, as_of: date) -> AccountBalance:
    rows = db.execute(
        select(Transaction.direction, func.coalesce(func.sum(Transaction.amount_paise), 0))
        .where(Transaction.account_id == account.id, Transaction.value_date <= as_of,
               Transaction.duplicate_of.is_(None))
        .group_by(Transaction.direction)
    ).all()
    credits = next((int(v) for d, v in rows if d == Direction.CREDIT), 0)
    debits = next((int(v) for d, v in rows if d == Direction.DEBIT), 0)
    last = db.scalar(
        select(func.max(Transaction.value_date))
        .where(Transaction.account_id == account.id, Transaction.value_date <= as_of))
    unverified = db.scalar(
        select(func.count()).select_from(Transaction)
        .where(Transaction.account_id == account.id, Transaction.value_date <= as_of,
               Transaction.evidence != Evidence.VERIFIED_ACTUAL)) or 0
    return AccountBalance(
        account_id=account.id, name=account.name, kind=account.kind,
        masked_number=account.masked_number,
        opening_paise=account.opening_balance_paise,
        credits_paise=credits, debits_paise=debits,
        closing_paise=account.opening_balance_paise + credits - debits,
        restricted_paise=account.restricted_paise,
        overdraft_limit_paise=account.overdraft_limit_paise,
        last_transaction_date=last.isoformat() if last else None,
        evidence=Evidence.IMPORTED_ACTUAL if unverified else Evidence.VERIFIED_ACTUAL,
    )


def committed_cash(db, business_id: str, as_of: date,
                   horizon_days: int = COMMITMENT_HORIZON_DAYS) -> tuple[int, list[dict]]:
    """Obligations the owner has asked us to ring-fence inside the horizon."""
    rows = db.scalars(select(Obligation).where(
        Obligation.business_id == business_id,
        Obligation.is_paid.is_(False),
        Obligation.reserve_cash.is_(True),
        Obligation.due_date >= as_of,
        Obligation.due_date <= as_of + timedelta(days=horizon_days),
    )).all()
    detail = [{"id": o.id, "kind": o.kind, "label": o.label,
               "due_date": o.due_date.isoformat(), "amount_paise": o.amount_paise,
               "evidence": o.evidence} for o in rows]
    return sum(o.amount_paise for o in rows), detail


def cash_position(db, business_id: str, as_of: date) -> CashPosition:
    accounts = db.scalars(select(Account).where(
        Account.business_id == business_id, Account.is_active.is_(True))).all()
    balances = [account_balance(db, a, as_of) for a in accounts]
    cash = sum(b.closing_paise for b in balances)
    restricted = sum(min(b.restricted_paise, max(0, b.closing_paise)) for b in balances)
    od_headroom = sum(b.overdraft_limit_paise for b in balances) - sum(
        max(0, -b.closing_paise) for b in balances)
    committed, detail = committed_cash(db, business_id, as_of)
    available = cash - restricted - committed
    verified = sum(1 for b in balances if b.evidence == Evidence.VERIFIED_ACTUAL)
    return CashPosition(
        as_of=as_of.isoformat(), cash_paise=cash, restricted_paise=restricted,
        committed_paise=committed, available_liquidity_paise=available,
        overdraft_headroom_paise=max(0, od_headroom),
        total_accessible_paise=available + max(0, od_headroom),
        accounts=[asdict(b) for b in balances], committed_breakdown=detail,
        verified_share=round(verified / len(balances), 3) if balances else 0.0,
    )


def daily_net_flow(db, business_id: str, start: date, end: date,
                   *, exclude_transfers: bool = True) -> dict[date, int]:
    """Net cash movement per day; internal transfers net to zero and are
    excluded so they do not inflate turnover statistics."""
    from app.core.enums import TxnCategory
    q = select(Transaction.value_date, Transaction.direction,
               func.sum(Transaction.amount_paise)).where(
        Transaction.business_id == business_id,
        Transaction.value_date >= start, Transaction.value_date <= end,
        Transaction.duplicate_of.is_(None))
    if exclude_transfers:
        q = q.where(Transaction.category != TxnCategory.TRANSFER)
    q = q.group_by(Transaction.value_date, Transaction.direction)
    out: dict[date, int] = {}
    for d, direction, amt in db.execute(q).all():
        if isinstance(d, str):
            d = date.fromisoformat(d)
        out[d] = out.get(d, 0) + (int(amt) if direction == Direction.CREDIT else -int(amt))
    return out


def flow_summary(db, business_id: str, as_of: date, days: int = 30) -> dict:
    """Inflow / outflow / net over a trailing window, split by category."""
    from app.core.enums import INFLOW_CATEGORIES, TxnCategory
    start = as_of - timedelta(days=days - 1)
    rows = db.execute(
        select(Transaction.category, Transaction.direction,
               func.sum(Transaction.amount_paise), func.count())
        .where(Transaction.business_id == business_id,
               Transaction.value_date >= start, Transaction.value_date <= as_of,
               Transaction.category != TxnCategory.TRANSFER,
               Transaction.duplicate_of.is_(None))
        .group_by(Transaction.category, Transaction.direction)).all()
    inflow = outflow = 0
    by_cat: dict[str, dict] = {}
    for cat, direction, amt, n in rows:
        amt = int(amt)
        if direction == Direction.CREDIT:
            inflow += amt
        else:
            outflow += amt
        e = by_cat.setdefault(cat, {"category": cat, "inflow_paise": 0, "outflow_paise": 0, "count": 0})
        e["inflow_paise" if direction == Direction.CREDIT else "outflow_paise"] += amt
        e["count"] += n
    cats = sorted(by_cat.values(), key=lambda c: -(c["inflow_paise"] + c["outflow_paise"]))
    return {"window_days": days, "start": start.isoformat(), "end": as_of.isoformat(),
            "inflow_paise": inflow, "outflow_paise": outflow, "net_paise": inflow - outflow,
            "by_category": cats}


def working_capital(db, business_id: str, as_of: date) -> dict:
    """Current assets (cash + AR) less current liabilities (AP + near-term
    obligations + 12 months of loan amortisation)."""
    pos = cash_position(db, business_id, as_of)
    ar = db.scalar(select(func.coalesce(func.sum(
        Invoice.total_paise - Invoice.settled_paise - Invoice.written_off_paise), 0)).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]),
        Invoice.issue_date <= as_of)) or 0
    ap = db.scalar(select(func.coalesce(func.sum(
        Invoice.total_paise - Invoice.settled_paise - Invoice.written_off_paise), 0)).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]),
        Invoice.issue_date <= as_of)) or 0
    oblig = db.scalar(select(func.coalesce(func.sum(Obligation.amount_paise), 0)).where(
        Obligation.business_id == business_id, Obligation.is_paid.is_(False),
        Obligation.due_date <= as_of + timedelta(days=90))) or 0
    loans = db.scalars(select(Loan).where(Loan.business_id == business_id,
                                          Loan.is_active.is_(True))).all()
    loan_current = sum(min(l.outstanding_paise, l.emi_paise * 12) for l in loans)
    ca = pos.cash_paise + int(ar)
    cl = int(ap) + int(oblig) + loan_current
    return {
        "current_assets_paise": ca, "current_liabilities_paise": cl,
        "working_capital_paise": ca - cl,
        "current_ratio": round(ca / cl, 3) if cl else None,
        "quick_ratio": round((pos.cash_paise + int(ar)) / cl, 3) if cl else None,
        "components": {"cash_paise": pos.cash_paise, "receivables_paise": int(ar),
                       "payables_paise": int(ap), "obligations_90d_paise": int(oblig),
                       "loan_current_portion_paise": loan_current},
    }
