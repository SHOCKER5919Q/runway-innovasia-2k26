"""The 13-week cash-flow model.

The forecast is **ledger-driven**, not a curve fitted to past balances. Each
week's movement is assembled from things that actually exist:

    closing[w] = closing[w-1]
               + collections from open sales invoices landing in week w
               + collections from sales not yet invoiced (run-rate x seasonality)
               - payments on open purchase invoices due in week w
               - purchases driven by the forecast sales (COGS, lead-shifted)
               - obligations (payroll, GST, rent, EMI, insurance) due in week w
               - recurring operating costs estimated from the trailing ledger

Why not fit a time-series model to the bank balance? Because an MSME's next
13 weeks are dominated by a few dozen *known* invoices and obligations whose
dates and amounts are already on file. A statistical extrapolation throws
that information away. Chronos-2 / LightGBM style forecasters are used where
they belong - on the **unknown** residual component (sales not yet invoiced),
which is exactly what ``revenue_runrate`` estimates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.core.enums import Direction, InvoiceKind, InvoiceStatus, ObligationKind, TxnCategory
from app.ledger.asof import outstanding_at, was_settled_by
from app.models import Counterparty, Invoice, Loan, Obligation, Transaction
from app.seed.profiles import get_profile

WEEK = 7


@dataclass
class ScheduledInflow:
    invoice_id: str
    counterparty_id: str
    amount_paise: int
    day_offset: float          # expected days from as_of
    sigma_days: float
    label: str


@dataclass
class ScheduledOutflow:
    label: str
    kind: str
    amount_paise: int
    day_offset: float
    sigma_days: float = 1.5
    flexible: bool = False     # can be deferred without breaching a contract
    source_id: str | None = None


@dataclass
class ForecastInputs:
    """Everything the simulator needs, fully serialisable.

    A scenario is literally a *copy of this object with fields changed*, which
    is what guarantees baseline and scenario are computed by the same code.
    """
    as_of: date
    horizon_weeks: int
    opening_cash_paise: int
    restricted_paise: int
    overdraft_limit_paise: int
    safety_buffer_paise: int
    inflows: list[ScheduledInflow] = field(default_factory=list)
    outflows: list[ScheduledOutflow] = field(default_factory=list)
    weekly_new_sales_paise: list[int] = field(default_factory=list)
    # Purchasing is committed ahead of the sale it supports: materials for the
    # next few weeks are already ordered, in transit, or under a minimum-order
    # commitment. A revenue shock therefore cuts collections long before it
    # cuts cash out. Without this, "revenue falls 20%" comes out as a *cash
    # improvement*, which is both wrong and dangerous to show an owner.
    baseline_weekly_sales_paise: list[int] = field(default_factory=list)
    committed_purchase_weeks: int = 0
    new_sales_collection_lag_days: float = 50.0
    new_sales_lag_sigma: float = 12.0
    cogs_ratio: float = 0.82
    cogs_lead_days: int = 12
    cogs_payment_days: int = 30
    weekly_opex_paise: int = 0
    opex_cv: float = 0.12
    revenue_cv: float = 0.22
    shock_weekly_rate: float = 0.06            # Poisson intensity of an unplanned expense
    shock_mean_paise: int = 60_000_00
    delay_correlation: float = 0.25            # common factor across customers
    # Weak demand and slow payment are the *same* event. When the market
    # turns, the order book thins and the debtors who still owe you start
    # stretching their terms. Modelling those two as independent - as most
    # spreadsheet cash flows do - understates the depth of the bad tail,
    # because it lets a path be simultaneously "down 20%" and "everyone paid
    # on time". ``revenue_delay_coupling`` is the strength of the shared
    # latent factor that prevents that: 0 disables it entirely.
    revenue_delay_coupling: float = 0.0
    assumptions: dict = field(default_factory=dict)

    def copy(self) -> "ForecastInputs":
        import copy as _c
        return _c.deepcopy(self)


def _weeks(as_of: date, n: int) -> list[date]:
    start = as_of - timedelta(days=as_of.weekday())
    return [start + timedelta(weeks=i) for i in range(n + 1)]


# ────────────────────────── input assembly ──────────────────────────

def revenue_runrate(db, business_id: str, as_of: date, weeks: int,
                    industry: str) -> tuple[list[int], dict]:
    """Expected weekly sales not yet invoiced.

    Estimator: a robust trailing weekly median over 12 weeks, de-seasonalised
    by the industry profile, re-seasonalised onto the forecast weeks, and
    nudged by the recent 4-week trend. Deliberately simple and auditable -
    with ~12 usable observations, anything heavier overfits.
    """
    prof = get_profile(industry)
    lookback = 26
    start = as_of - timedelta(weeks=lookback)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= start, Invoice.issue_date <= as_of)).all()
    buckets: dict[date, int] = {}
    for i in invs:
        wk = i.issue_date - timedelta(days=i.issue_date.weekday())
        buckets[wk] = buckets.get(wk, 0) + i.total_paise
    keys = sorted(buckets)[:-1]            # drop the partial current week
    if len(keys) < 4:
        return [0] * weeks, {"method": "insufficient history", "observations": len(keys)}

    vals = np.array([buckets[k] for k in keys], dtype=float)
    seas = np.array([prof.seasonality[k.month - 1] for k in keys], dtype=float)
    deseason = vals / seas
    base = float(np.median(deseason[-12:]))
    recent = float(np.median(deseason[-4:]))
    older = float(np.median(deseason[-12:-4])) if len(deseason) >= 12 else base
    trend = np.clip(recent / older, 0.80, 1.20) if older > 0 else 1.0

    out, detail = [], []
    for w in _weeks(as_of, weeks)[1:]:
        mult = prof.seasonality[w.month - 1]
        # Taper the trend: a 4-week trend should not be extrapolated 13 weeks.
        k = len(out) + 1
        damp = 1.0 + (trend - 1.0) * float(np.exp(-k / 8.0))
        v = int(base * mult * damp)
        out.append(v)
        detail.append({"week_start": w.isoformat(), "seasonality": round(mult, 3),
                       "trend_damped": round(damp, 3), "paise": v})
    meta = {
        "method": "robust de-seasonalised weekly median with damped 4-week trend",
        "observations": len(keys),
        "baseline_weekly_paise": int(base),
        "raw_trend_ratio": round(float(trend), 3),
        "cv": round(float(np.std(deseason[-12:]) / max(1.0, base)), 3),
        "weekly": detail,
    }
    return out, meta


def recurring_opex(db, business_id: str, as_of: date, lookback_days: int = 180) -> tuple[int, dict]:
    """Weekly run-rate of operating costs that are not invoices or obligations."""
    cats = [TxnCategory.UTILITIES, TxnCategory.FREIGHT, TxnCategory.BANK_CHARGES,
            TxnCategory.OTHER_EXPENSE, TxnCategory.GATEWAY_FEE, TxnCategory.REFUND_OUT]
    start = as_of - timedelta(days=lookback_days)
    rows = db.scalars(select(Transaction).where(
        Transaction.business_id == business_id, Transaction.direction == Direction.DEBIT,
        Transaction.category.in_(cats),
        Transaction.value_date >= start, Transaction.value_date <= as_of)).all()
    total = sum(t.amount_paise for t in rows)
    weeks = max(1.0, lookback_days / 7.0)
    by_cat: dict[str, int] = {}
    for t in rows:
        by_cat[t.category] = by_cat.get(t.category, 0) + t.amount_paise
    return int(total / weeks), {
        "lookback_days": lookback_days, "transactions": len(rows),
        "weekly_paise": int(total / weeks),
        "by_category": {k: int(v / weeks) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "method": "trailing mean of non-invoice operating debits",
    }


COUPLING_CAP = 0.60
"""Upper bound on the estimated revenue/payment-delay coupling.

Deliberately below 1: the estimate is a correlation over a handful of
monthly observations and must not be allowed to dominate the simulation.
"""


def estimate_revenue_delay_coupling(db, business_id: str, as_of: date,
                                    months: int = 15) -> tuple[float, dict]:
    """How strongly weak months and slow-paying months coincide.

    For each of the last ``months`` calendar months we take the value of
    sales invoices *issued* in that month and the mean days-late of those
    same invoices once they settled. A negative correlation between the two
    is the signature we care about: when billing is thin, customers stretch.

    The estimate is a plain Pearson correlation over at most ~15 points, so
    it is reported with its sample size and floored at zero - a *positive*
    estimate (busy months are also slow months) is treated as no evidence of
    a downturn effect rather than as a reason to shorten payment times.
    """
    start = (as_of.replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= start, Invoice.issue_date <= as_of)).all()
    by_month: dict[str, dict] = {}
    for i in invs:
        k = i.issue_date.strftime("%Y-%m")
        m = by_month.setdefault(k, {"billed": 0.0, "n": 0, "delay_sum": 0.0, "n_delay": 0})
        m["billed"] += i.total_paise
        m["n"] += 1
        if i.settled_date and was_settled_by(i, as_of):
            m["delay_sum"] += float((i.settled_date - i.due_date).days)
            m["n_delay"] += 1
    rows = [(k, v) for k, v in sorted(by_month.items()) if v["n_delay"] >= 1]
    meta = {"method": "Pearson correlation of monthly billing vs mean days-late",
            "months_observed": len(rows)}
    if len(rows) < 6:
        meta.update({"estimate": None, "coupling": 0.0,
                     "note": "too few settled months to estimate; coupling disabled"})
        return 0.0, meta
    billed = np.array([v["billed"] for _, v in rows], dtype=float)
    delay = np.array([v["delay_sum"] / v["n_delay"] for _, v in rows], dtype=float)
    sb, sd = billed.std(), delay.std()
    if sb <= 0 or sd <= 0:
        meta.update({"estimate": None, "coupling": 0.0,
                     "note": "no variation in monthly billing or delay; coupling disabled"})
        return 0.0, meta
    corr = float(np.corrcoef(billed, delay)[0, 1])
    coupling = float(np.clip(max(0.0, -corr), 0.0, COUPLING_CAP))
    meta.update({
        "estimate": round(corr, 3),
        "coupling": round(coupling, 3),
        "months_used": len(rows),
        "note": ("Coupling is the negative part of the correlation, capped at "
                 f"{COUPLING_CAP}. A positive correlation is read as no downturn "
                 "signal and floors at zero."),
        "series": [{"month": k, "billed_paise": int(v["billed"]),
                    "mean_delay_days": round(v["delay_sum"] / v["n_delay"], 1),
                    "settled_invoices": v["n_delay"]} for k, v in rows],
    })
    return coupling, meta


def build_inputs(db, business_id: str, as_of: date, *, horizon_weeks: int = 13,
                 predictions: dict[str, dict] | None = None,
                 safety_buffer_paise: int = 0, industry: str = "wholesale_distribution",
                 ) -> ForecastInputs:
    from app.analytics.cash import cash_position
    from app.analytics.payables import msmed_deadline

    pos = cash_position(db, business_id, as_of)
    prof = get_profile(industry)

    # ---- open receivables --------------------------------------------
    # Point-in-time: an invoice settled after ``as_of`` was still open then.
    sales = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]))).all()
    inflows: list[ScheduledInflow] = []
    for inv in sales:
        out = outstanding_at(inv, as_of)
        if out <= 0:
            continue
        p = (predictions or {}).get(inv.id)
        if p:
            pay = date.fromisoformat(p["predicted_pay_date"])
            sigma = float(p.get("sigma_days", 10.0))
        else:
            pay = max(inv.due_date, as_of)
            sigma = 12.0
        inflows.append(ScheduledInflow(
            invoice_id=inv.id, counterparty_id=inv.counterparty_id, amount_paise=out,
            day_offset=max(0.0, (pay - as_of).days), sigma_days=max(1.0, sigma),
            label=f"{inv.invoice_no}"))

    # ---- open payables ------------------------------------------------
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    purchases = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.WRITTEN_OFF]))).all()
    outflows: list[ScheduledOutflow] = []
    for inv in purchases:
        out = outstanding_at(inv, as_of)
        if out <= 0:
            continue
        cp = parties.get(inv.counterparty_id)
        dl = msmed_deadline(inv, cp)
        effective = min([d for d in (inv.due_date, dl) if d is not None])
        outflows.append(ScheduledOutflow(
            label=f"{inv.invoice_no} - {cp.name if cp else 'supplier'}",
            kind="supplier_invoice", amount_paise=out,
            day_offset=max(0.0, (effective - as_of).days), sigma_days=2.0,
            flexible=(dl is None), source_id=inv.id))

    # ---- obligations ---------------------------------------------------
    obs = db.scalars(select(Obligation).where(
        Obligation.business_id == business_id, Obligation.is_paid.is_(False),
        Obligation.due_date >= as_of,
        Obligation.due_date <= as_of + timedelta(weeks=horizon_weeks))).all()
    for o in obs:
        outflows.append(ScheduledOutflow(
            label=o.label, kind=o.kind, amount_paise=o.amount_paise,
            day_offset=max(0.0, (o.due_date - as_of).days), sigma_days=1.0,
            flexible=o.kind in (ObligationKind.OTHER, ObligationKind.INSURANCE),
            source_id=o.id))

    # Recurring monthly items beyond the obligations already on file: the
    # generator only materialises a couple of months ahead, but payroll and
    # rent do not stop. Projecting them is what keeps the forecast honest.
    known_months = {(o.due_date.year, o.due_date.month, o.kind) for o in obs}
    recurring_seed = [o for o in obs if o.is_recurring]
    cursor = as_of.replace(day=1)
    for _ in range(4):
        cursor = (cursor + timedelta(days=32)).replace(day=1)
        if cursor > as_of + timedelta(weeks=horizon_weeks):
            break
        for o in recurring_seed:
            if (cursor.year, cursor.month, o.kind) in known_months:
                continue
            try:
                due = cursor.replace(day=min(o.due_date.day, 28))
            except ValueError:
                continue
            if not (as_of < due <= as_of + timedelta(weeks=horizon_weeks)):
                continue
            known_months.add((cursor.year, cursor.month, o.kind))
            outflows.append(ScheduledOutflow(
                label=f"{o.label.split(' - ')[0]} - {cursor.strftime('%B %Y')} (projected)",
                kind=o.kind, amount_paise=o.amount_paise,
                day_offset=(due - as_of).days, sigma_days=2.0, flexible=False,
                source_id=None))

    # Loan EMIs not already captured as obligations
    for ln in db.scalars(select(Loan).where(Loan.business_id == business_id,
                                            Loan.is_active.is_(True))).all():
        cur = as_of
        for _ in range(horizon_weeks // 4 + 2):
            try:
                due = cur.replace(day=min(ln.emi_day, 28))
            except ValueError:
                break
            if due <= as_of:
                cur = (cur + timedelta(days=32)).replace(day=1)
                continue
            if due > as_of + timedelta(weeks=horizon_weeks):
                break
            if any(o.kind == ObligationKind.LOAN_EMI and abs(o.day_offset - (due - as_of).days) < 4
                   for o in outflows):
                cur = (cur + timedelta(days=32)).replace(day=1)
                continue
            outflows.append(ScheduledOutflow(
                label=f"{ln.lender} EMI {due:%b %Y}", kind=ObligationKind.LOAN_EMI,
                amount_paise=ln.emi_paise, day_offset=(due - as_of).days,
                sigma_days=0.5, flexible=False, source_id=ln.id))
            cur = (cur + timedelta(days=32)).replace(day=1)

    new_sales, rr_meta = revenue_runrate(db, business_id, as_of, horizon_weeks, industry)
    opex, opex_meta = recurring_opex(db, business_id, as_of)

    # Average realised collection lag, used for sales not yet invoiced.
    settled = [i for i in db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.settled_date.isnot(None),
        Invoice.issue_date >= as_of - timedelta(days=365))).all()
        if was_settled_by(i, as_of)]
    lags = [float((i.settled_date - i.issue_date).days) for i in settled]
    lag = float(np.median(lags)) if lags else float(prof.default_customer_credit_days + 10)
    lag_sd = float(np.std(lags)) if len(lags) > 2 else 12.0

    coupling, coupling_meta = estimate_revenue_delay_coupling(db, business_id, as_of)

    return ForecastInputs(
        as_of=as_of, horizon_weeks=horizon_weeks,
        # Restricted balances are excluded: a lien-marked FD cannot pay payroll.
        opening_cash_paise=pos.cash_paise - pos.restricted_paise,
        restricted_paise=pos.restricted_paise,
        overdraft_limit_paise=pos.overdraft_headroom_paise,
        safety_buffer_paise=safety_buffer_paise,
        inflows=inflows, outflows=outflows,
        weekly_new_sales_paise=new_sales,
        baseline_weekly_sales_paise=list(new_sales),
        committed_purchase_weeks=max(1, round((prof.cogs_lead_days +
                                               prof.default_supplier_credit_days) / 7)),
        new_sales_collection_lag_days=lag, new_sales_lag_sigma=max(5.0, lag_sd),
        revenue_delay_coupling=coupling,
        cogs_ratio=1.0 - prof.gross_margin, cogs_lead_days=prof.cogs_lead_days,
        cogs_payment_days=prof.default_supplier_credit_days,
        weekly_opex_paise=opex, revenue_cv=rr_meta.get("cv", prof.revenue_cv) or prof.revenue_cv,
        assumptions={
            "opening_cash_excludes_restricted_paise": pos.restricted_paise,
            "open_receivables_count": len(inflows),
            "open_receivables_paise": sum(i.amount_paise for i in inflows),
            "scheduled_outflows_count": len(outflows),
            "scheduled_outflows_paise": sum(o.amount_paise for o in outflows),
            "revenue_runrate": rr_meta,
            "recurring_opex": opex_meta,
            "collection_lag_days_median": round(lag, 1),
            "collection_lag_sd": round(lag_sd, 1),
            "revenue_delay_coupling": coupling_meta,
            "cogs_ratio": round(1.0 - prof.gross_margin, 4),
            "industry_profile": prof.label,
            "payment_predictions_used": bool(predictions),
            "committed_purchase_weeks": max(1, round((prof.cogs_lead_days +
                                                      prof.default_supplier_credit_days) / 7)),
            "note": ("Receivables are scheduled from invoice-level predicted payment "
                     "dates. Sales not yet invoiced are a separate, clearly-labelled "
                     "run-rate component."),
        })
