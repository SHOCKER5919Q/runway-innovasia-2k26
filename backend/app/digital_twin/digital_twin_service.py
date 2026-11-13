"""Assembles the complete twin bundle that the API and copilot read from.

One computation per (business, as_of, ledger fingerprint), cached in process.
Everything downstream - dashboard, briefing, risk centre, copilot tools -
reads the *same* bundle, which is what stops two screens showing two
different answers to the same question.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.models import ActualSnapshot, Business, Invoice, PredictedSnapshot

_CACHE: dict[tuple, tuple[float, "TwinBundle"]] = {}
_LOCK = threading.Lock()
CACHE_TTL_SECONDS = 180


@dataclass
class TwinBundle:
    business: Any
    as_of: date
    actual_state: Any
    predicted_state: Any
    actual_snapshot: Any
    predicted_snapshot: Any
    position: Any
    simulation: Any
    forecast_inputs: Any
    predictions: dict
    behaviour: list
    collection_list: list
    ageing_ar: dict
    ageing_ap: dict
    supplier_profiles: list
    payment_calendar: list
    msmed: dict
    concentration: dict
    correlation: dict
    obligations: dict
    coverage: dict
    health: dict
    anomalies: list
    stress: list
    sensitivity: list
    findings: list
    recommendations: list
    working_capital: dict
    flow_30d: dict
    data_quality: dict
    built_ms: int = 0
    extra: dict = field(default_factory=dict)


def invalidate(business_id: str | None = None) -> None:
    with _LOCK:
        if business_id is None:
            _CACHE.clear()
        else:
            for k in [k for k in _CACHE if k[0] == business_id]:
                _CACHE.pop(k, None)


def get_bundle(db, business_id: str, as_of: date, *, force: bool = False,
               heavy: bool = True) -> TwinBundle:
    from app.financial_states.state_manager import ledger_fingerprint

    fp = ledger_fingerprint(db, business_id, as_of)
    key = (business_id, as_of.isoformat(), fp, heavy)

    def cached():
        with _LOCK:
            hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
        return None

    if not force and (b := cached()):
        return b

    # One build per business at a time. A page load fires several requests at
    # once; without this each of them built the same bundle in parallel, and
    # the concurrent state writes raced for SQLite's single write lock. Late
    # arrivals now wait, then find the bundle the first request just cached.
    with _build_lock(business_id):
        if not force and (b := cached()):
            return b
        bundle = _build(db, business_id, as_of, heavy=heavy)
        with _LOCK:
            _CACHE[key] = (time.time(), bundle)
            if len(_CACHE) > 24:
                for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:8]:
                    _CACHE.pop(k, None)
    return bundle


_BUILD_LOCKS: dict[str, threading.Lock] = {}


def _build_lock(business_id: str) -> threading.Lock:
    with _LOCK:
        return _BUILD_LOCKS.setdefault(business_id, threading.Lock())


def _build(db, business_id: str, as_of: date, *, heavy: bool) -> TwinBundle:
    from app.analytics import anomaly, concentration as conc_mod, health as health_mod
    from app.analytics.cash import cash_position, flow_summary, working_capital
    from app.analytics.obligations import calendar, coverage as cov_mod
    from app.analytics.payables import msmed_exposure, payment_calendar, supplier_profiles
    from app.analytics.receivables import ageing, collection_priority, customer_behaviour
    from app.financial_states.state_manager import (
        _inputs_from_snapshot, build_actual, build_predicted, data_quality)
    from app.forecast.monte_carlo import SimulationResult, sensitivity as sens_mod, simulate
    from app.recommend.engine import generate
    from app.risk import early_warning, stress as stress_mod
    from app.core.enums import InvoiceKind
    from app.models import PaymentPrediction

    t0 = time.perf_counter()
    biz = db.get(Business, business_id)
    actual = build_actual(db, business_id, as_of, trigger="bundle")
    predicted, psnap = build_predicted(db, business_id, actual, trigger="bundle")
    db.commit()

    asnap = db.get(ActualSnapshot, actual.id)
    series = psnap.series_json or {}
    simulation = SimulationResult(**series) if series else None

    preds = {p.invoice_id: {
        "invoice_id": p.invoice_id,
        "predicted_pay_date": p.predicted_pay_date.isoformat(),
        "predicted_delay_days_p10": p.predicted_delay_days_p10,
        "predicted_delay_days_p50": p.predicted_delay_days_p50,
        "predicted_delay_days_p90": p.predicted_delay_days_p90,
        "prob_within_7": p.prob_within_7, "prob_within_15": p.prob_within_15,
        "prob_within_30": p.prob_within_30, "prob_default": p.prob_default,
        "confidence": p.confidence, "drivers": p.drivers_json,
        "model_version": p.model_version,
        "sigma_days": max(1.0, (p.predicted_delay_days_p90 - p.predicted_delay_days_p10) / 2.5631),
    } for p in db.scalars(select(PaymentPrediction).where(
        PaymentPrediction.predicted_state_id == predicted.id)).all()}

    fi = _inputs_from_snapshot(db, business_id, actual, psnap)
    position = cash_position(db, business_id, as_of)
    behaviour = customer_behaviour(db, business_id, as_of)
    collection = collection_priority(db, business_id, as_of, predictions=preds, limit=30)
    ar_age = ageing(db, business_id, as_of, InvoiceKind.SALES)
    ap_age = ageing(db, business_id, as_of, InvoiceKind.PURCHASE)
    suppliers = supplier_profiles(db, business_id, as_of)
    paycal = payment_calendar(db, business_id, as_of)
    msmed = msmed_exposure(db, business_id, as_of)
    conc = conc_mod.concentration(db, business_id, as_of)
    corr = conc_mod.correlated_exposure(db, business_id, as_of)
    obligations = calendar(db, business_id, as_of)
    expected_in = int(sum(simulation.inflow_p50[1:8])) if simulation else 0
    coverage = cov_mod(db, business_id, as_of, 45, expected_inflow_paise=expected_in)
    health = health_mod.compute(db, business_id, as_of, simulation=simulation)
    anomalies = anomaly.detect(db, business_id, as_of, ensemble=False)
    wc = working_capital(db, business_id, as_of)
    f30 = flow_summary(db, business_id, as_of, 30)
    dq = data_quality(db, business_id, as_of)

    stress = stress_mod.run_all(fi, simulation, paths=1500) if (heavy and simulation) else []
    sens = sens_mod(fi, paths=1000) if heavy else []

    findings = early_warning.evaluate(
        business=biz, as_of=as_of, position=position, simulation=simulation,
        behaviour=behaviour, ageing_ar=ar_age, concentration=conc,
        obligations=obligations, coverage=coverage, msmed=msmed, anomalies=anomalies,
        health=health, supplier_profiles=suppliers)
    recs = generate(
        business=biz, as_of=as_of, position=position, simulation=simulation,
        behaviour=behaviour, collection_list=collection, ageing_ar=ar_age,
        concentration=conc, coverage=coverage, msmed=msmed,
        supplier_profiles=suppliers, health=health, anomalies=anomalies,
        stress_results=stress, obligations=obligations)

    # An empty ledger has nothing to warn about or recommend: anything here
    # would come from default assumptions and random shocks, not the business.
    if not dq.get("transactions") and not ar_age.get("total_paise") \
            and not (ap_age or {}).get("total_paise"):
        findings, recs = [], []

    _persist_alerts(db, business_id, findings, actual.id)
    _persist_recs(db, business_id, recs, actual.id)
    db.commit()

    return TwinBundle(
        business=biz, as_of=as_of, actual_state=actual, predicted_state=predicted,
        actual_snapshot=asnap, predicted_snapshot=psnap, position=position,
        simulation=simulation, forecast_inputs=fi, predictions=preds,
        behaviour=behaviour, collection_list=collection, ageing_ar=ar_age,
        ageing_ap=ap_age, supplier_profiles=suppliers, payment_calendar=paycal,
        msmed=msmed, concentration=conc, correlation=corr, obligations=obligations,
        coverage=coverage, health=health, anomalies=anomalies, stress=stress,
        sensitivity=sens, findings=findings, recommendations=recs,
        working_capital=wc, flow_30d=f30, data_quality=dq,
        built_ms=int((time.perf_counter() - t0) * 1000))


def _persist_alerts(db, business_id: str, findings, state_id: str) -> None:
    from app.models import Alert
    existing = {a.dedupe_key: a for a in db.scalars(select(Alert).where(
        Alert.business_id == business_id, Alert.is_open.is_(True))).all()}
    seen = set()
    for f in findings:
        seen.add(f.dedupe_key)
        a = existing.get(f.dedupe_key)
        if a:
            a.level, a.title = f.level, f.title
            a.what_happened, a.why_it_matters = f.what_happened, f.why_it_matters
            a.evidence_json = f.evidence
            a.impact_paise, a.impact_date = f.impact_paise, f.impact_date
            a.recommended_action, a.if_ignored = f.recommended_action, f.if_ignored
            a.state_id = state_id
        else:
            db.add(Alert(
                business_id=business_id, code=f.code, level=f.level, title=f.title,
                what_happened=f.what_happened, why_it_matters=f.why_it_matters,
                evidence_json=f.evidence, impact_paise=f.impact_paise,
                impact_date=f.impact_date, recommended_action=f.recommended_action,
                if_ignored=f.if_ignored, state_id=state_id, dedupe_key=f.dedupe_key))
    for key, a in existing.items():
        if key not in seen:
            a.is_open = False   # resolved: the condition no longer holds


def _persist_recs(db, business_id: str, recs, state_id: str) -> None:
    from app.models import Recommendation
    # One row per recommendation code, keeping the owner's decision. This used
    # to look only at open/accepted rows, so a dismissed or done item got a
    # fresh "open" twin on the next build and the decision vanished.
    existing = {}
    for r in db.scalars(select(Recommendation).where(
            Recommendation.business_id == business_id)).all():
        keep = existing.get(r.code)
        if keep is None or (keep.status == "open" and r.status != "open"):
            if keep is not None:
                db.delete(keep)
            existing[r.code] = r
        else:
            db.delete(r)
    seen = set()
    for r in recs:
        seen.add(r.code)
        row = existing.get(r.code)
        if row is None:
            row = Recommendation(business_id=business_id, code=r.code)
            db.add(row)
        row.title, row.priority = r.title, r.priority
        row.score_json = r.score_terms
        row.trigger_evidence_json = r.trigger_evidence
        row.expected_effect_paise = r.expected_effect_paise
        row.expected_effect_text = r.expected_effect_text
        row.downside_text = r.downside_text
        row.required_action = r.required_action
        row.deadline, row.confidence = r.deadline, r.confidence
        row.explanation, row.state_id = r.explanation, state_id
        row.requires_approval = r.requires_approval
    for code, row in existing.items():
        if code not in seen and row.status == "open":
            row.status = "dismissed"
