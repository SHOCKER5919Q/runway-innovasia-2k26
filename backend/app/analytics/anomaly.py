"""Transaction anomaly detection.

Three complementary detectors, all interpretable - an MSME owner has to be
able to see *why* a transaction was flagged or the alert is worthless:

1. **Robust z-score within a category** (median / MAD). Resistant to the
   outliers it is looking for, unlike mean/sd.
2. **Duplicate-payment detector** - same counterparty, same amount, close
   together, no shared bank reference.
3. **Category spend change-point** - a CUSUM-style test on weekly spend per
   category, which catches a drift that no single transaction reveals.

Isolation Forest is deliberately *not* the primary detector: it scores well
but cannot explain itself, and an unexplainable alert about someone's money
destroys trust. It is available as a cross-check via ``ensemble=True``.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.core.enums import Direction, TxnCategory
from app.models import Counterparty, Transaction

MAD_SCALE = 1.4826   # makes MAD a consistent estimator of sigma for normal data
Z_THRESHOLD = 4.0
MIN_SAMPLES = 12


def robust_z(values: np.ndarray) -> np.ndarray:
    med = np.median(values)
    mad = np.median(np.abs(values - med))
    scale = MAD_SCALE * mad
    if scale <= 0:
        scale = values.std() or 1.0
    return (values - med) / scale


def detect(db, business_id: str, as_of: date, lookback_days: int = 365,
           recent_days: int = 60, *, ensemble: bool = False) -> list[dict]:
    since = as_of - timedelta(days=lookback_days)
    txns = db.scalars(select(Transaction).where(
        Transaction.business_id == business_id,
        Transaction.value_date >= since, Transaction.value_date <= as_of,
        Transaction.category != TxnCategory.TRANSFER)).all()
    parties = {c.id: c.name for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    recent_cutoff = as_of - timedelta(days=recent_days)
    findings: list[dict] = []

    # ── 1. size outliers within a category ────────────────────────────
    by_cat: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_cat[t.category].append(t)
    for cat, rows in by_cat.items():
        if len(rows) < MIN_SAMPLES:
            continue
        amounts = np.array([t.amount_paise for t in rows], dtype=float)
        z = robust_z(amounts)
        med = float(np.median(amounts))
        for t, zi in zip(rows, z):
            if zi > Z_THRESHOLD and t.value_date >= recent_cutoff:
                findings.append({
                    "kind": "amount_outlier", "severity": "warning" if zi > 6 else "watch",
                    "transaction_id": t.id, "date": t.value_date.isoformat(),
                    "amount_paise": t.amount_paise, "category": cat,
                    "counterparty": parties.get(t.counterparty_id),
                    "narration": t.narration[:160],
                    "score": round(float(zi), 2),
                    "why": (f"{t.amount_paise/100:,.0f} is {zi:.1f} robust standard deviations "
                            f"above the median {cat.replace('_',' ')} of "
                            f"Rs {med/100:,.0f} across {len(rows)} transactions."),
                })

    # ── 2. probable duplicate payments ────────────────────────────────
    buckets: dict[tuple, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.direction != Direction.DEBIT or t.value_date < recent_cutoff - timedelta(days=60):
            continue
        buckets[(t.counterparty_id, t.amount_paise)].append(t)
    for (cp_id, amt), rows in buckets.items():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda t: t.value_date)
        for a, b in zip(rows, rows[1:]):
            gap = (b.value_date - a.value_date).days
            if gap > 7:
                continue
            if a.reference_no and b.reference_no and a.reference_no != b.reference_no:
                continue   # distinct bank references: most likely two real payments
            findings.append({
                "kind": "possible_duplicate_payment", "severity": "warning",
                "transaction_id": b.id, "related_transaction_id": a.id,
                "date": b.value_date.isoformat(), "amount_paise": amt,
                "category": b.category, "counterparty": parties.get(cp_id),
                "narration": b.narration[:160], "score": round(1.0 - gap / 8.0, 2),
                "why": (f"Two debits of Rs {amt/100:,.0f} to the same counterparty "
                        f"{gap} day(s) apart with no distinguishing bank reference. "
                        f"Confirm before treating either as settled."),
            })

    # ── 3. category spend change-points ───────────────────────────────
    weekly: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for t in txns:
        if t.direction != Direction.DEBIT:
            continue
        wk = t.value_date - timedelta(days=t.value_date.weekday())
        weekly[t.category][wk] += t.amount_paise
    for cat, series in weekly.items():
        weeks = sorted(series)
        if len(weeks) < 16:
            continue
        vals = np.array([series[w] for w in weeks], dtype=float)
        base, recent = vals[:-6], vals[-6:]
        if base.size < 8 or base.mean() <= 0:
            continue
        shift = (recent.mean() - base.mean()) / base.mean()
        sd = base.std() or 1.0
        t_stat = (recent.mean() - base.mean()) / (sd / np.sqrt(recent.size))
        if abs(shift) >= 0.35 and abs(t_stat) >= 2.5:
            findings.append({
                "kind": "spend_shift", "severity": "watch",
                "transaction_id": None, "date": weeks[-1].isoformat(),
                "amount_paise": int(recent.mean() - base.mean()),
                "category": cat, "counterparty": None,
                "narration": f"{cat.replace('_',' ').title()} weekly spend",
                "score": round(float(abs(t_stat)), 2),
                "why": (f"Weekly {cat.replace('_',' ')} spend has moved {shift:+.0%} over the "
                        f"last 6 weeks (Rs {base.mean()/100:,.0f} to Rs {recent.mean()/100:,.0f}, "
                        f"t={t_stat:+.1f}). Confirm whether this is intended."),
            })

    if ensemble:
        findings.extend(_isolation_forest(txns, recent_cutoff, parties))

    order = {"critical": 0, "warning": 1, "watch": 2, "info": 3}
    findings.sort(key=lambda f: (order.get(f["severity"], 9), -f["score"]))
    return findings


def _isolation_forest(txns, recent_cutoff, parties) -> list[dict]:
    """Unsupervised cross-check. Reported as 'info' only, because it cannot
    say *why* something is unusual."""
    try:
        from sklearn.ensemble import IsolationForest
    except Exception:
        return []
    rows = [t for t in txns if t.amount_paise > 0]
    if len(rows) < 80:
        return []
    X = np.column_stack([
        np.log1p([t.amount_paise for t in rows]),
        [t.value_date.weekday() for t in rows],
        [t.value_date.day for t in rows],
        [1.0 if t.direction == Direction.CREDIT else 0.0 for t in rows],
    ])
    clf = IsolationForest(n_estimators=200, contamination=0.01, random_state=42).fit(X)
    scores = -clf.score_samples(X)
    thresh = float(np.quantile(scores, 0.99))
    out = []
    for t, s in zip(rows, scores):
        if s >= thresh and t.value_date >= recent_cutoff:
            out.append({
                "kind": "unsupervised_outlier", "severity": "info",
                "transaction_id": t.id, "date": t.value_date.isoformat(),
                "amount_paise": t.amount_paise, "category": t.category,
                "counterparty": parties.get(t.counterparty_id),
                "narration": t.narration[:160], "score": round(float(s), 3),
                "why": ("Flagged by an isolation forest over amount, weekday, day-of-month "
                        "and direction. This detector cannot explain its reasoning - treat "
                        "it as a prompt to look, not as a finding."),
            })
    return out
