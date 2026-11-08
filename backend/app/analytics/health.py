"""Business Financial Health Score.

A transparent 0-100 composite over eight dimensions. Every sub-score states
its inputs, its thresholds and the arithmetic, and the weights live in
``HealthConfig`` so a user or an industry profile can change them.

**This is not a credit score.** It is not produced by a credit bureau, it has
no regulatory standing, and no lender is obliged to recognise it. It exists
so that an owner can see which part of their finances moved and why.

Scoring shape: each dimension maps a measured ratio onto 0-100 through a
piecewise-linear curve anchored on values that mean something operationally
(e.g. "8 weeks of runway" rather than an arbitrary z-score).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.core.enums import Direction, InvoiceKind, TxnCategory
from app.models import Invoice, Loan, Transaction


@dataclass
class HealthConfig:
    weights: dict[str, float] = field(default_factory=lambda: {
        "liquidity": 0.20,
        "receivables_quality": 0.16,
        "cashflow_stability": 0.14,
        "debt_service": 0.12,
        "customer_concentration": 0.10,
        "revenue_consistency": 0.10,
        "working_capital_efficiency": 0.10,
        "obligation_coverage": 0.08,
    })
    target_runway_weeks: float = 8.0
    healthy_current_ratio: float = 1.5
    healthy_dso_days: float = 45.0
    max_concentration: float = 0.35
    healthy_dscr: float = 1.5


BANDS = [(80, "Strong"), (65, "Healthy"), (50, "Fair"), (35, "Stretched"), (0, "Critical")]


def _band(score: float) -> str:
    return next(label for lo, label in BANDS if score >= lo)


def _lerp(x: float, lo: float, hi: float) -> float:
    """Map x in [lo, hi] onto 0..100, clamped."""
    if hi == lo:
        return 50.0
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0) * 100.0)


def compute(db, business_id: str, as_of: date, *, simulation=None,
            config: HealthConfig | None = None) -> dict:
    from app.analytics.cash import cash_position, working_capital
    from app.analytics.concentration import concentration
    from app.analytics.receivables import ageing, customer_behaviour

    cfg = config or HealthConfig()
    pos = cash_position(db, business_id, as_of)
    wc = working_capital(db, business_id, as_of)
    conc = concentration(db, business_id, as_of)
    age = ageing(db, business_id, as_of)
    subs: list[dict] = []

    # ── 1. liquidity ───────────────────────────────────────────────
    runway = simulation.runway_weeks_p50 if simulation else None
    if runway is None:
        weekly_burn = _weekly_burn(db, business_id, as_of)
        runway = (pos.available_liquidity_paise / weekly_burn) if weekly_burn > 0 else 13.0
    liq = 0.6 * _lerp(min(runway, 26), 0, cfg.target_runway_weeks * 2) + \
          0.4 * _lerp(wc["current_ratio"] or 0, 0.6, cfg.healthy_current_ratio + 0.5)
    subs.append(_sub("liquidity", "Liquidity", liq, cfg, [
        f"Median forecast runway {runway:.1f} weeks against a target of {cfg.target_runway_weeks:.0f}",
        f"Current ratio {wc['current_ratio']}, target {cfg.healthy_current_ratio}",
        f"Available liquidity Rs {pos.available_liquidity_paise/100:,.0f} "
        f"(cash Rs {pos.cash_paise/100:,.0f} less restricted and committed)"]))

    # ── 2. receivables quality ─────────────────────────────────────
    behaviour = customer_behaviour(db, business_id, as_of)
    overdue_share = age["overdue_share"]
    w_delay = (sum(c.mean_delay_days * c.outstanding_paise for c in behaviour) /
               max(1, sum(c.outstanding_paise for c in behaviour))) if behaviour else 0.0
    beyond60 = sum(b["amount_paise"] for b in age["buckets"][3:]) / max(1, age["total_paise"])
    recv = (0.40 * _lerp(1 - overdue_share, 0.4, 1.0)
            + 0.35 * _lerp(30 - w_delay, -20, 30)
            + 0.25 * _lerp(1 - beyond60, 0.85, 1.0))
    subs.append(_sub("receivables_quality", "Receivables quality", recv, cfg, [
        f"{overdue_share:.0%} of the receivables book is past due",
        f"Exposure-weighted mean delay {w_delay:+.1f} days against terms",
        f"{beyond60:.1%} of receivables are more than 60 days past due"]))

    # ── 3. cash-flow stability ─────────────────────────────────────
    weekly = _weekly_net(db, business_id, as_of, weeks=26)
    if len(weekly) >= 8:
        arr = np.array(weekly, dtype=float)
        scale = np.median(np.abs(arr)) or 1.0
        cv = float(np.std(arr) / scale)
        # Downside deviation: only shortfalls count as instability. Adapted
        # from the Sortino ratio - upside volatility is not a problem.
        downside = arr[arr < 0]
        dd = float(np.sqrt(np.mean(downside ** 2))) if downside.size else 0.0
        stab = 0.6 * _lerp(3.0 - cv, 0.0, 3.0) + 0.4 * _lerp(1 - dd / (3 * scale), 0.0, 1.0)
        ev = [f"Weekly net cash flow CV {cv:.2f} over {len(weekly)} weeks",
              f"Downside deviation Rs {dd/100:,.0f} per week",
              "Only negative weeks count towards instability (Sortino-style)"]
    else:
        stab, ev = 50.0, ["Fewer than 8 weeks of history - stability not measurable"]
    subs.append(_sub("cashflow_stability", "Cash-flow stability", stab, cfg, ev))

    # ── 4. debt service ────────────────────────────────────────────
    loans = db.scalars(select(Loan).where(Loan.business_id == business_id,
                                          Loan.is_active.is_(True))).all()
    emi_m = sum(l.emi_paise for l in loans)
    op_cash_m = _operating_cash_monthly(db, business_id, as_of)
    dscr = (op_cash_m / emi_m) if emi_m > 0 else None
    debt = 100.0 if dscr is None else _lerp(dscr, 0.6, cfg.healthy_dscr + 0.5)
    subs.append(_sub("debt_service", "Debt obligations", debt, cfg, [
        (f"Debt service coverage {dscr:.2f}x (monthly operating cash "
         f"Rs {op_cash_m/100:,.0f} / EMI Rs {emi_m/100:,.0f}), target "
         f"{cfg.healthy_dscr}x") if dscr is not None else "No active loan obligations",
        f"Total loan outstanding Rs {sum(l.outstanding_paise for l in loans)/100:,.0f}"]))

    # ── 5. customer concentration ──────────────────────────────────
    top1 = conc["top1_share"]
    cc = 0.6 * _lerp(cfg.max_concentration + 0.25 - top1, 0.0, cfg.max_concentration + 0.25) + \
         0.4 * _lerp(0.45 - conc["counterparty_hhi"], 0.0, 0.45)
    subs.append(_sub("customer_concentration", "Customer concentration", cc, cfg, [
        f"Largest customer is {top1:.0%} of revenue; policy limit {cfg.max_concentration:.0%}",
        f"HHI {conc['counterparty_hhi']:.3f} ({conc['counterparty_band']}), "
        f"equivalent to {conc['effective_counterparties']} equally-sized customers",
        f"Top three customers are {conc['top3_share']:.0%} of revenue"]))

    # ── 6. revenue consistency ─────────────────────────────────────
    monthly = _monthly_revenue(db, business_id, as_of, months=12)
    if len(monthly) >= 6:
        a = np.array(monthly, dtype=float)
        cvr = float(np.std(a) / max(1.0, np.mean(a)))
        recent = float(np.mean(a[-3:])); prior = float(np.mean(a[-6:-3]))
        growth = (recent / prior - 1.0) if prior > 0 else 0.0
        rev = 0.6 * _lerp(0.45 - cvr, 0.0, 0.45) + 0.4 * _lerp(growth + 0.15, 0.0, 0.30)
        ev = [f"Monthly revenue CV {cvr:.2f} over {len(monthly)} months",
              f"Last 3 months vs prior 3: {growth:+.1%}"]
    else:
        rev, ev = 50.0, ["Fewer than 6 months of revenue history"]
    subs.append(_sub("revenue_consistency", "Revenue consistency", rev, cfg, ev))

    # ── 7. working-capital efficiency (cash conversion cycle) ──────
    dso = _dso(db, business_id, as_of)
    dpo = _dpo(db, business_id, as_of)
    ccc = (dso or 0) - (dpo or 0)
    # Anchors: a cash conversion gap of <= 0 days is excellent (the business
    # is funded by its suppliers); 75 days is where working capital starts
    # dictating every decision.
    eff = _lerp(75 - ccc, 0, 90)
    subs.append(_sub("working_capital_efficiency", "Working-capital efficiency", eff, cfg, [
        f"DSO {dso:.0f} days, DPO {dpo:.0f} days",
        f"Cash conversion gap {ccc:+.0f} days (inventory days not tracked - "
        f"no stock data connected)",
        "A positive gap means the business funds its buyers before its suppliers fund it"]))

    # ── 8. obligation coverage ─────────────────────────────────────
    from app.analytics.obligations import coverage as oblig_coverage
    expected_in = None
    if simulation is not None:
        n = min(len(simulation.inflow_p50) - 1, 7)   # ~45 days
        expected_in = int(sum(simulation.inflow_p50[1:n + 1]))
    cov = oblig_coverage(db, business_id, as_of, horizon_days=45,
                         expected_inflow_paise=expected_in)
    ratio = cov["coverage_ratio"]
    oc = _lerp(ratio, 0.5, 1.6)
    subs.append(_sub("obligation_coverage", "Statutory & payroll coverage", oc, cfg, [
        f"Liquidity plus expected collections covers {ratio:.2f}x the next 45 days "
        f"of obligations (cash alone: {cov['coverage_ratio_cash_only']:.2f}x)",
        f"Rs {cov['total_paise']/100:,.0f} due, of which Rs {cov['statutory_paise']/100:,.0f} statutory",
        f"Expected collections basis: {cov['expected_collections_basis']}"]))

    total = round(sum(s["score"] * s["weight"] for s in subs), 1)
    return {
        "as_of": as_of.isoformat(), "score": total, "band": _band(total),
        "subscores": subs,
        "weights": cfg.weights,
        "methodology": {
            "version": "health-1.1.0",
            "shape": "weighted mean of eight piecewise-linear dimension scores on 0-100",
            "configurable": True,
            "disclaimer": ("This is RUNWAY's own transparent indicator built from this "
                           "business's ledger. It is NOT a credit score, is not issued by "
                           "a credit bureau and has no regulatory standing."),
        },
    }


def _sub(key: str, label: str, score: float, cfg: HealthConfig, evidence: list[str]) -> dict:
    s = round(float(np.clip(score, 0, 100)), 1)
    return {"key": key, "label": label, "score": s, "band": _band(s),
            "weight": cfg.weights[key], "contribution": round(s * cfg.weights[key], 2),
            "evidence": evidence}


# ── helpers ────────────────────────────────────────────────────────

def _weekly_net(db, business_id: str, as_of: date, weeks: int = 26) -> list[int]:
    from app.analytics.cash import daily_net_flow
    start = as_of - timedelta(weeks=weeks)
    daily = daily_net_flow(db, business_id, start, as_of)
    buckets: dict[date, int] = {}
    for d, v in daily.items():
        wk = d - timedelta(days=d.weekday())
        buckets[wk] = buckets.get(wk, 0) + v
    return [buckets[k] for k in sorted(buckets)[:-1]]


def _weekly_burn(db, business_id: str, as_of: date) -> float:
    w = _weekly_net(db, business_id, as_of, weeks=12)
    neg = [-x for x in w if x < 0]
    return float(np.mean(neg)) if neg else 0.0


def _operating_cash_monthly(db, business_id: str, as_of: date, months: int = 6) -> float:
    """Accrual operating surplus per month - an EBITDA proxy.

    Deliberately *not* net bank movement: a growing or seasonal business can
    post a strongly negative cash month purely because it funded working
    capital, and a DSCR built on that would read 0.00x for a perfectly
    solvent company. Lenders assess coverage on earnings, so RUNWAY does too.
    """
    start = (as_of - timedelta(days=31 * months)).replace(day=1)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.issue_date >= start, Invoice.issue_date <= as_of)).all()
    sales = sum(i.taxable_paise for i in invs if i.kind == InvoiceKind.SALES)
    cogs = sum(i.taxable_paise for i in invs if i.kind == InvoiceKind.PURCHASE)
    opex_cats = [TxnCategory.PAYROLL, TxnCategory.RENT, TxnCategory.UTILITIES,
                 TxnCategory.FREIGHT, TxnCategory.BANK_CHARGES, TxnCategory.GATEWAY_FEE,
                 TxnCategory.OTHER_EXPENSE, TxnCategory.PF_ESI]
    opex = sum(t.amount_paise for t in db.scalars(select(Transaction).where(
        Transaction.business_id == business_id, Transaction.direction == Direction.DEBIT,
        Transaction.category.in_(opex_cats),
        Transaction.value_date >= start, Transaction.value_date <= as_of)).all())
    n = max(1.0, (as_of - start).days / 30.44)
    return max(0.0, (sales - cogs - opex) / n)


def _monthly_revenue(db, business_id: str, as_of: date, months: int = 12) -> list[int]:
    start = (as_of - timedelta(days=31 * months)).replace(day=1)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= start, Invoice.issue_date <= as_of)).all()
    b: dict[tuple[int, int], int] = {}
    for i in invs:
        k = (i.issue_date.year, i.issue_date.month)
        b[k] = b.get(k, 0) + i.taxable_paise
    keys = sorted(b)[:-1]
    return [b[k] for k in keys]


def _dso(db, business_id: str, as_of: date, days: int = 90) -> float:
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= as_of - timedelta(days=days), Invoice.issue_date <= as_of)).all()
    billed = sum(i.total_paise for i in invs)
    outstanding = sum(i.outstanding_paise for i in db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date <= as_of)).all())
    return round(outstanding / (billed / days), 1) if billed else 0.0


def _dpo(db, business_id: str, as_of: date, days: int = 90) -> float:
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date >= as_of - timedelta(days=days), Invoice.issue_date <= as_of)).all()
    billed = sum(i.total_paise for i in invs)
    outstanding = sum(i.outstanding_paise for i in db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.PURCHASE,
        Invoice.issue_date <= as_of)).all())
    return round(outstanding / (billed / days), 1) if billed else 0.0
