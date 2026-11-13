"""Import history: what every upload changed, kept for good.

The ledger is append-only, like a bank passbook: an import adds rows, a
re-upload of the same file is caught as duplicates, and nothing earlier is
overwritten. What was missing was the *effect* of each upload. Every real
(non-dry-run) import now records the business's headline figures just before
and just after it, on the batch itself, so an owner can open any past upload
and see exactly what it moved - and compare today's numbers with any earlier
point.
"""
from __future__ import annotations

from datetime import date

from app.digital_twin.digital_twin_service import get_bundle, invalidate

FIELDS = [
    ("transactions", "Transactions on the ledger", "count"),
    ("cash_in_hand_paise", "Cash in hand", "paise"),
    ("available_paise", "Available cash", "paise"),
    ("receivables_paise", "Receivables", "paise"),
    ("payables_paise", "Payables", "paise"),
    ("inflow_30d_paise", "30-day inflow", "paise"),
    ("outflow_30d_paise", "30-day outflow", "paise"),
    ("runway_weeks_p10", "Runway P10 (weeks)", "weeks"),
    ("breach_probability", "Buffer breach probability", "probability"),
    ("health_score", "Health score", "score"),
]


def snapshot(db, business_id: str, as_of: date) -> dict:
    """Headline figures for one business at one as-of date."""
    try:
        b = get_bundle(db, business_id, as_of, force=True)
    except Exception as e:  # an empty workspace cannot build a twin yet
        return {"available": False, "reason": f"{type(e).__name__}: {e}"[:200]}
    p, s = b.position, b.simulation
    return {
        "available": True,
        "as_of": as_of.isoformat(),
        "transactions": int(b.data_quality.get("transactions", 0)),
        "cash_in_hand_paise": int(p.cash_paise),
        "available_paise": int(p.available_liquidity_paise),
        "receivables_paise": int(b.ageing_ar.get("total_paise", 0)),
        "payables_paise": int(b.ageing_ap.get("total_paise", 0)),
        "inflow_30d_paise": int(b.flow_30d.get("inflow_paise", 0)),
        "outflow_30d_paise": int(b.flow_30d.get("outflow_paise", 0)),
        "runway_weeks_p10": round(float(s.runway_weeks_p10), 2) if s else None,
        "breach_probability": round(float(s.breach_probability), 4) if s else None,
        "health_score": round(float(b.health.get("score", 0)), 1),
        "ledger_fingerprint": b.actual_state.ledger_fingerprint,
    }


def diff(before: dict, after: dict) -> list[dict]:
    rows = []
    for key, label, unit in FIELDS:
        a, c = before.get(key), after.get(key)
        rows.append({"key": key, "label": label, "unit": unit, "before": a, "after": c,
                     "change": (c - a) if isinstance(a, (int, float)) and
                     isinstance(c, (int, float)) else None})
    return rows


def import_with_impact(db, import_fn, *, business_id: str, as_of: date, **kwargs) -> dict:
    """Run ``import_fn`` (integrations.service.import_file) and record its effect."""
    before = snapshot(db, business_id, as_of)
    db.rollback()                      # the snapshot may have written state rows
    result = import_fn(db, business_id=business_id, today=as_of, **kwargs)
    if kwargs.get("dry_run"):
        return result
    db.commit()
    invalidate(business_id)
    after = snapshot(db, business_id, as_of)
    from app.models import ImportBatch
    batch = db.get(ImportBatch, result["batch_id"])
    if batch is not None:
        impact = {"as_of": as_of.isoformat(), "before": before, "after": after,
                  "changes": diff(before, after) if before.get("available")
                  and after.get("available") else []}
        batch.report_json = {**(batch.report_json or {}), "impact": impact}
        db.commit()
        result["impact"] = impact
    return result
