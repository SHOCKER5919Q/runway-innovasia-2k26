"""Leakage-safe feature construction for the payment-delay model.

The single most common way to get a convincing-but-useless payment-delay
model is to build customer features from the *whole* dataset. A customer's
"average delay" then contains information from invoices issued after the one
being predicted, and the test score looks excellent while the live model is
worthless.

Every customer feature here is built in a strict chronological pass and only
ever sees invoices whose **settlement** was already known on the issue date
of the invoice being featurised. ``tests/test_no_leakage.py`` asserts this.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from app.core.enums import InvoiceKind, InvoiceStatus
from app.ledger.asof import outstanding_at, was_settled_by

FEATURE_NAMES = [
    "credit_days",
    "log_amount",
    "amount_vs_customer_mean",
    "cust_prior_count",
    "cust_mean_delay",
    "cust_median_delay",
    "cust_delay_sd",
    "cust_recent3_mean_delay",
    "cust_recent6_mean_delay",
    "cust_delay_trend_per_month",
    "cust_on_time_rate",
    "cust_partial_rate",
    "cust_tenure_days",
    "cust_open_exposure_ratio",
    "due_month_sin",
    "due_month_cos",
    "due_is_month_end",
    "due_weekday",
    "issue_to_due_quarter_end",
    "global_prior_mean_delay",
    "months_since_first_invoice_in_book",
]


@dataclass
class FeatureRow:
    invoice_id: str
    counterparty_id: str
    issue_date: date
    due_date: date
    settled_date: date | None
    outstanding_paise: int
    total_paise: int
    x: np.ndarray
    y: float | None       # realised delay in days, None while unsettled


def _month_end(d: date) -> bool:
    nxt = date(d.year + (d.month == 12), (d.month % 12) + 1, 1)
    return (nxt - d).days <= 3


def build_features(invoices: list, as_of: date) -> list[FeatureRow]:
    """One chronological sweep over sales invoices.

    Ordering key is the *issue* date: when invoice i is featurised we may use
    any invoice that was both issued and settled strictly before i's issue
    date. Invoices settled later are invisible, exactly as they would be in
    production.
    """
    sales = sorted(
        [i for i in invoices if i.kind == InvoiceKind.SALES and i.issue_date <= as_of],
        key=lambda i: (i.issue_date, i.invoice_no),
    )
    # Settlement events indexed by the date they became known.
    settled_events = sorted(
        [(i.settled_date, i.counterparty_id, float((i.settled_date - i.due_date).days),
          (i.first_payment_date != i.settled_date) if i.first_payment_date else False,
          i.total_paise)
         for i in sales if was_settled_by(i, as_of)],
        key=lambda t: t[0],
    )

    # Running open exposure per customer: incremented when an invoice is
    # issued, decremented when it settles. A proxy for "how much is already
    # riding on this buyer right now".
    open_exposure: dict[str, int] = {}
    hist: dict[str, list[float]] = {}
    partials: dict[str, list[int]] = {}
    amounts: dict[str, list[float]] = {}
    first_seen: dict[str, date] = {}
    all_delays: list[float] = []
    ev_idx = 0

    book_start = sales[0].issue_date if sales else as_of
    rows: list[FeatureRow] = []
    for inv in sales:
        while ev_idx < len(settled_events) and settled_events[ev_idx][0] < inv.issue_date:
            _, cp, delay, was_partial, amt = settled_events[ev_idx]
            hist.setdefault(cp, []).append(delay)
            partials.setdefault(cp, []).append(1 if was_partial else 0)
            amounts.setdefault(cp, []).append(float(amt))
            all_delays.append(delay)
            # The invoice has now been collected, so it stops counting towards
            # this customer's open exposure.
            open_exposure[cp] = max(0, open_exposure.get(cp, 0) - int(amt))
            ev_idx += 1

        cp = inv.counterparty_id
        first_seen.setdefault(cp, inv.issue_date)
        h = hist.get(cp, [])
        n = len(h)
        arr = np.array(h, dtype=float) if n else np.array([], dtype=float)
        gmean = float(np.mean(all_delays)) if all_delays else 0.0

        cust_mean = float(arr.mean()) if n else gmean
        cust_med = float(np.median(arr)) if n else gmean
        cust_sd = float(arr.std()) if n > 1 else 0.0
        recent3 = float(arr[-3:].mean()) if n else gmean
        recent6 = float(arr[-6:].mean()) if n else gmean
        # Slope of this customer's recent payment behaviour. A buyer drifting
        # later month on month is the signal a flat per-customer average
        # structurally cannot see.
        if n >= 6:
            w = arr[-10:]
            t = np.arange(len(w), dtype=float)
            trend = float(np.polyfit(t, w, 1)[0]) * 4.0   # per ~month of invoices
        else:
            trend = 0.0
        on_time = float((arr <= 0).mean()) if n else 0.5
        p = partials.get(cp, [])
        partial_rate = float(np.mean(p)) if p else 0.0
        tenure = float((inv.issue_date - first_seen[cp]).days)
        av = amounts.get(cp, [])
        cust_amount_mean = float(np.mean(av)) if av else float(inv.total_paise)
        amount_ratio = float(inv.total_paise) / max(1.0, cust_amount_mean)
        exposure = open_exposure.get(cp, 0)
        exposure_ratio = float(exposure / max(1, inv.total_paise))

        due = inv.due_date
        x = np.array([
            float(inv.credit_days),
            float(np.log1p(inv.total_paise / 100.0)),
            min(20.0, amount_ratio),
            float(n),
            cust_mean, cust_med, cust_sd, recent3, recent6,
            float(np.clip(trend, -15.0, 15.0)), on_time, partial_rate,
            tenure, min(50.0, exposure_ratio),
            float(np.sin(2 * np.pi * due.month / 12)),
            float(np.cos(2 * np.pi * due.month / 12)),
            1.0 if _month_end(due) else 0.0,
            float(due.weekday()),
            1.0 if due.month in (3, 6, 9, 12) and _month_end(due) else 0.0,
            gmean,
            float((inv.issue_date - book_start).days / 30.44),
        ], dtype=float)

        # Only settlements that had already happened by ``as_of`` are visible.
        settled = inv.settled_date if was_settled_by(inv, as_of) else None
        y = float((settled - inv.due_date).days) if settled else None
        rows.append(FeatureRow(
            invoice_id=inv.id, counterparty_id=cp, issue_date=inv.issue_date,
            due_date=inv.due_date, settled_date=settled,
            outstanding_paise=outstanding_at(inv, as_of), total_paise=inv.total_paise,
            x=x, y=y,
        ))
        open_exposure[cp] = exposure + inv.total_paise
    return rows


def open_invoice_rows(rows: list[FeatureRow]) -> list[FeatureRow]:
    return [r for r in rows if r.outstanding_paise > 0]


def settled_rows(rows: list[FeatureRow]) -> list[FeatureRow]:
    return [r for r in rows if r.y is not None]
