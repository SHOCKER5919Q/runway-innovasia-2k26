"""Portfolio-style concentration analysis applied to counterparties.

Borrowed from market risk: the Herfindahl-Hirschman Index measures how much
of an exposure sits in few hands. In an equity portfolio it flags single-name
risk; here it flags the MSME failure mode where one buyer going quiet takes
the business down with it.

HHI = sum of squared shares, on 0..1. The usual antitrust reading is:
  < 0.15 unconcentrated, 0.15-0.25 moderate, > 0.25 high.
``effective_n = 1 / HHI`` is the equivalent number of equally-sized
counterparties, which owners find far easier to act on than the index itself.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.core.enums import InvoiceKind
from app.models import Counterparty, Invoice


def hhi(shares: list[float]) -> float:
    s = float(sum(shares))
    if s <= 0:
        return 0.0
    return float(sum((x / s) ** 2 for x in shares))


def _band(h: float) -> str:
    return "high" if h > 0.25 else ("moderate" if h > 0.15 else "low")


def concentration(db, business_id: str, as_of: date, *, kind: str = InvoiceKind.SALES,
                  lookback_days: int = 365) -> dict:
    since = as_of - timedelta(days=lookback_days)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == kind,
        Invoice.issue_date >= since, Invoice.issue_date <= as_of)).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}

    by_cp: dict[str, int] = {}
    by_sector: dict[str, int] = {}
    by_region: dict[str, int] = {}
    outstanding: dict[str, int] = {}
    for i in invs:
        by_cp[i.counterparty_id] = by_cp.get(i.counterparty_id, 0) + i.total_paise
        outstanding[i.counterparty_id] = outstanding.get(i.counterparty_id, 0) + i.outstanding_paise
        cp = parties.get(i.counterparty_id)
        if cp:
            by_sector[cp.sector or "Unclassified"] = by_sector.get(cp.sector or "Unclassified", 0) + i.total_paise
            by_region[cp.region or "Unclassified"] = by_region.get(cp.region or "Unclassified", 0) + i.total_paise

    total = sum(by_cp.values()) or 1
    ranked = sorted(by_cp.items(), key=lambda kv: -kv[1])
    top = [{"counterparty_id": cid,
            "name": parties[cid].name if cid in parties else "Unknown",
            "volume_paise": v, "share": round(v / total, 4),
            "outstanding_paise": outstanding.get(cid, 0)} for cid, v in ranked[:12]]

    h_cp = hhi(list(by_cp.values()))
    h_sec = hhi(list(by_sector.values()))
    h_reg = hhi(list(by_region.values()))
    top1 = ranked[0][1] / total if ranked else 0.0
    top3 = sum(v for _, v in ranked[:3]) / total if ranked else 0.0

    return {
        "as_of": as_of.isoformat(), "kind": kind, "lookback_days": lookback_days,
        "total_volume_paise": total,
        "counterparty_hhi": round(h_cp, 4), "counterparty_band": _band(h_cp),
        "effective_counterparties": round(1 / h_cp, 2) if h_cp else None,
        "sector_hhi": round(h_sec, 4), "sector_band": _band(h_sec),
        "region_hhi": round(h_reg, 4), "region_band": _band(h_reg),
        "top1_share": round(top1, 4), "top3_share": round(top3, 4),
        "top_counterparties": top,
        "by_sector": [{"label": k, "volume_paise": v, "share": round(v / total, 4)}
                      for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])],
        "by_region": [{"label": k, "volume_paise": v, "share": round(v / total, 4)}
                      for k, v in sorted(by_region.items(), key=lambda kv: -kv[1])],
        "interpretation": (
            f"The equivalent of {1/h_cp:.1f} equally-sized counterparties carry this book. "
            f"The largest single counterparty is {top1:.0%} of volume."
            if h_cp else "Not enough data."),
    }


def correlated_exposure(db, business_id: str, as_of: date, lookback_days: int = 365) -> dict:
    """Do our largest customers move together?

    If several big buyers sit in the same sector *and* their monthly payment
    delays are correlated, then a single sector event hits all of them at
    once - and the naive assumption that delays are independent understates
    the risk badly. This feeds the correlation structure used by the Monte
    Carlo engine.
    """
    since = as_of - timedelta(days=lookback_days)
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES,
        Invoice.issue_date >= since, Invoice.settled_date.isnot(None))).all()
    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}

    series: dict[str, dict[str, list[float]]] = {}
    for i in invs:
        key = f"{i.settled_date.year}-{i.settled_date.month:02d}"
        series.setdefault(i.counterparty_id, {}).setdefault(key, []).append(
            float((i.settled_date - i.due_date).days))
    months = sorted({m for v in series.values() for m in v})
    names, matrix = [], []
    for cid, bym in series.items():
        if len(bym) < 6:
            continue
        row = [float(np.mean(bym[m])) if m in bym else np.nan for m in months]
        if sum(1 for x in row if not np.isnan(x)) < 6:
            continue
        names.append(parties[cid].name if cid in parties else cid[:8])
        matrix.append(row)
    if len(matrix) < 2:
        return {"available": False,
                "reason": "need at least two customers with six months of settled invoices",
                "months": months, "pairs": []}

    arr = np.array(matrix, dtype=float)
    # Pairwise-complete Pearson correlation on monthly mean delay.
    n = len(names)
    pairs = []
    for a in range(n):
        for b in range(a + 1, n):
            mask = ~np.isnan(arr[a]) & ~np.isnan(arr[b])
            if mask.sum() < 5:
                continue
            x, y = arr[a][mask], arr[b][mask]
            if x.std() == 0 or y.std() == 0:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            pairs.append({"a": names[a], "b": names[b], "r": round(r, 3),
                          "months": int(mask.sum())})
    pairs.sort(key=lambda p: -abs(p["r"]))
    rs = [p["r"] for p in pairs]
    return {
        "available": True, "months": months, "customers": names,
        "pairs": pairs[:20],
        "mean_pairwise_r": round(float(np.mean(rs)), 3) if rs else 0.0,
        "max_pairwise_r": round(max(rs), 3) if rs else 0.0,
        "interpretation": (
            "Payment delays move together across customers; treating them as "
            "independent would understate the chance of a simultaneous shortfall."
            if rs and float(np.mean(rs)) > 0.25 else
            "Payment delays are largely independent across customers in this sample."),
    }
