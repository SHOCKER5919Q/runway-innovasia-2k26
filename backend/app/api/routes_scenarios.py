"""Scenario Lab: build, run, branch, compare and record decisions."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import jsonable, money, today_param
from app.api.deps import DbDep, Tenant, audit
from app.core.enums import DecisionStatus, Role, ScenarioKind
from app.digital_twin.digital_twin_service import get_bundle
from app.digital_twin.scenario_engine import CATALOGUE, ScenarioError
from app.financial_states.state_manager import long_horizon_check, run_scenario
from app.models import Scenario, ScenarioDecision, SimulatedSnapshot, _uid

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
AsOf = Annotated[date, Depends(today_param)]


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str
    parameters: dict = Field(default_factory=dict)
    description: str = ""
    parent_scenario_id: str | None = None
    run_now: bool = True


@router.get("/catalogue")
def catalogue(db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    cat = []
    for c in CATALOGUE:
        entry = {**c, "params": [dict(p) for p in c["params"]]}
        for p in entry["params"]:
            if p["kind"] == "select" and p["key"] == "counterparty_id":
                p["options"] = ([{"value": "largest", "label": "Largest by open exposure"}]
                                + [{"value": x.counterparty_id, "label": x.name}
                                   for x in b.behaviour])
        cat.append(entry)
    return jsonable({"catalogue": cat,
                     "isolation": ("A scenario edits an in-memory copy of the forecast "
                                   "inputs. It cannot write to the ledger: there is no "
                                   "code path from the scenario engine to a ledger table."),
                     "reproducibility": ("Baseline and scenario share a random seed, so "
                                         "the difference between them is the decision, "
                                         "not simulation noise.")})


@router.get("")
def list_scenarios(db: DbDep, ctx: Tenant, include_archived: bool = False):
    q = select(Scenario).where(Scenario.business_id == ctx.business_id)
    if not include_archived:
        q = q.where(Scenario.is_archived.is_(False))
    rows = db.scalars(q.order_by(Scenario.created_at.desc())).all()
    out = []
    for s in rows:
        snap = db.get(SimulatedSnapshot, s.last_run_state_id) if s.last_run_state_id else None
        dec = db.scalar(select(ScenarioDecision).where(ScenarioDecision.scenario_id == s.id))
        out.append({
            "id": s.id, "name": s.name, "kind": s.kind, "description": s.description,
            "parameters": s.parameters_json, "origin": s.origin,
            "parent_scenario_id": s.parent_scenario_id,
            "created_at": s.created_at.isoformat(),
            "last_run_state_id": s.last_run_state_id,
            "summary": {
                "runway_weeks_p50": snap.runway_weeks_p50,
                "min_cash_p50": money(snap.min_cash_p50_paise),
                "min_cash_p10": money(snap.min_cash_p10_paise),
                "breach_probability": snap.breach_probability,
                "expected_profit": money(snap.expected_profit_paise),
                "financing_cost": money(snap.financing_cost_paise),
                "peak_working_capital": money(snap.peak_wc_requirement_paise),
            } if snap else None,
            "decision": {"status": dec.status,
                         "implementation_date": dec.implementation_date.isoformat()
                                                if dec.implementation_date else None,
                         "note": dec.note} if dec else None,
        })
    return jsonable({"scenarios": out})


@router.post("", status_code=201)
def create_scenario(body: ScenarioIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    ctx.require(Role.MANAGER)
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    s = Scenario(id=_uid(), business_id=ctx.business_id, name=body.name, kind=body.kind,
                 description=body.description, parameters_json=body.parameters,
                 baseline_actual_state_id=b.actual_state.id,
                 baseline_predicted_state_id=b.predicted_state.id,
                 parent_scenario_id=body.parent_scenario_id,
                 created_by_user_id=ctx.user.id, origin="ui")
    db.add(s)
    db.add(ScenarioDecision(id=_uid(), business_id=ctx.business_id, scenario_id=s.id,
                            status=DecisionStatus.DRAFT))
    audit(db, ctx, "scenario.create", entity="scenario", entity_id=s.id,
          detail={"kind": body.kind, "params": body.parameters})
    db.commit()
    if body.run_now:
        # Called directly, so Query defaults must be supplied explicitly.
        return run_scenario_endpoint(s.id, db, ctx, as_of, paths=2500, seed=None)
    return jsonable({"id": s.id, "name": s.name, "kind": s.kind, "ran": False})


@router.post("/{scenario_id}/run")
def run_scenario_endpoint(scenario_id: str, db: DbDep, ctx: Tenant, as_of: AsOf,
                          paths: int = Query(2500, ge=200, le=20000),
                          seed: int | None = None):
    s = db.get(Scenario, scenario_id)
    if not s or s.business_id != ctx.business_id:
        raise HTTPException(404, "Scenario not found")
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    # Pin to the baseline the scenario was created against so a saved
    # comparison stays honest even after the ledger has moved on.
    from app.models import BusinessState
    actual = db.get(BusinessState, s.baseline_actual_state_id) or b.actual_state
    predicted = db.get(BusinessState, s.baseline_predicted_state_id) or b.predicted_state
    try:
        state, snap, payload = run_scenario(db, s, actual=actual, predicted=predicted,
                                            paths=paths, seed=seed)
    except ScenarioError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return jsonable({
        "scenario": {"id": s.id, "name": s.name, "kind": s.kind,
                     "parameters": s.parameters_json},
        "simulated_state_id": state.id, "state_version": state.version,
        "baseline_state_ids": {"actual": actual.id, "predicted": predicted.id},
        "baseline_is_current": actual.id == b.actual_state.id,
        "comparison": payload["comparison"],
        "economics": payload["economics"],
        "scenario_series": payload["scenario"],
        "baseline_series": payload["baseline"],
        "summary": {
            "runway_weeks_p50": snap.runway_weeks_p50,
            "min_cash_p50": money(snap.min_cash_p50_paise),
            "min_cash_p10": money(snap.min_cash_p10_paise),
            "peak_working_capital": money(snap.peak_wc_requirement_paise),
            "breach_probability": snap.breach_probability,
            "expected_profit": money(snap.expected_profit_paise),
            "financing_cost": money(snap.financing_cost_paise)},
        "long_horizon": long_horizon_check(db, ctx.business_id, as_of,
                                           s.kind, s.parameters_json or {}),
        "isolation_guarantee": ("Nothing was written to the ledger. A simulated payment "
                                "is not a payment, and a simulated loan is not a liability."),
    })


class QuickRunIn(BaseModel):
    kind: str
    parameters: dict = Field(default_factory=dict)
    paths: int = Field(default=2500, ge=200, le=20000)


@router.post("/quick-run")
def quick_run(body: QuickRunIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Run a scenario without saving it - the Scenario Lab slider path."""
    from app.core.config import settings
    from app.digital_twin.scenario_engine import apply_scenario
    from app.financial_states.state_manager import compare_simulations
    from app.forecast.monte_carlo import simulate
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    try:
        fi, extras = apply_scenario(b.forecast_inputs, body.kind, body.parameters, as_of)
    except ScenarioError as e:
        raise HTTPException(422, str(e))
    base = simulate(b.forecast_inputs, paths=body.paths, seed=settings.monte_carlo_seed)
    scen = simulate(fi, paths=body.paths, seed=settings.monte_carlo_seed)
    return jsonable({
        "kind": body.kind, "parameters": body.parameters,
        "comparison": compare_simulations(base, scen, extras),
        "economics": extras, "scenario_series": scen.dict(), "baseline_series": base.dict(),
        # For scenarios that change the sales run-rate, a 13-week window sees
        # the purchases before the collections they fund. The second quarter
        # is computed too rather than the bias merely being disclosed.
        "long_horizon": long_horizon_check(db, ctx.business_id, as_of,
                                           body.kind, body.parameters),
        "saved": False,
        "isolation_guarantee": "Nothing was written to the ledger or saved.",
    })


class CompareIn(BaseModel):
    scenario_ids: list[str] = Field(min_length=1, max_length=8)


@router.post("/compare")
def compare(body: CompareIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    base = b.simulation
    rows = []
    for sid in body.scenario_ids:
        s = db.get(Scenario, sid)
        if not s or s.business_id != ctx.business_id:
            raise HTTPException(404, f"Scenario {sid} not found")
        snap = db.get(SimulatedSnapshot, s.last_run_state_id) if s.last_run_state_id else None
        if snap is None:
            raise HTTPException(409, f"Scenario '{s.name}' has not been run yet")
        out = (snap.outputs_json or {}).get("scenario", {})
        rows.append({
            "scenario_id": s.id, "name": s.name, "kind": s.kind,
            "parameters": s.parameters_json,
            "baseline_actual_state_id": snap.baseline_actual_state_id,
            "min_cash_p50": money(snap.min_cash_p50_paise),
            "min_cash_p10": money(snap.min_cash_p10_paise),
            "closing_cash_p50": money(out.get("p50", [0])[-1] if out.get("p50") else 0),
            "runway_weeks_p50": snap.runway_weeks_p50,
            "breach_probability": snap.breach_probability,
            "peak_working_capital": money(snap.peak_wc_requirement_paise),
            "expected_profit": money(snap.expected_profit_paise),
            "financing_cost": money(snap.financing_cost_paise),
            "p50": out.get("p50"), "p10": out.get("p10"),
            "week_starts": out.get("week_starts"),
            "economics": (snap.outputs_json or {}).get("economics", {}),
        })
    baselines = {r["baseline_actual_state_id"] for r in rows}
    return jsonable({
        "as_of": as_of.isoformat(),
        "baseline": {"name": "Baseline (no change)",
                     "min_cash_p50": money(base.min_cash_p50_paise),
                     "min_cash_p10": money(base.min_cash_p10_paise),
                     "closing_cash_p50": money(base.p50[-1]),
                     "runway_weeks_p50": base.runway_weeks_p50,
                     "breach_probability": base.breach_probability,
                     "p50": base.p50, "p10": base.p10,
                     "week_starts": base.week_starts} if base else None,
        "scenarios": rows,
        "all_share_baseline": len(baselines) == 1,
        "warning": (None if len(baselines) == 1 else
                    "These scenarios were run against different baselines, so the "
                    "comparison is indicative rather than exact. Re-run them to align."),
        "best_by_min_cash": max(rows, key=lambda r: r["min_cash_p10"]["paise"])["name"] if rows else None,
    })


class OptimiseIn(BaseModel):
    options: list[dict] = Field(min_length=2, max_length=8)
    risk_appetite: str | None = None
    paths: int = Field(default=2000, ge=200, le=10000)


@router.post("/optimise")
def optimise(body: OptimiseIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Rank several candidate decisions on a risk-adjusted objective."""
    from app.digital_twin.decision_optimizer import Option, evaluate
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    opts = [Option(key=o.get("key", f"opt{i}"), label=o.get("label", f"Option {i+1}"),
                   kind=o["kind"], params=o.get("params", {}), note=o.get("note", ""))
            for i, o in enumerate(body.options)]
    res = evaluate(b.forecast_inputs, opts, as_of,
                   risk_appetite=body.risk_appetite or b.business.risk_appetite,
                   paths=body.paths,
                   policies={"min_cash_paise": b.business.safety_buffer_paise,
                             "max_borrowing_apr": b.business.max_borrowing_apr,
                             "min_order_margin": b.business.min_order_margin,
                             "max_breach_probability": 0.40})
    return jsonable(res)


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: DbDep, ctx: Tenant):
    s = db.get(Scenario, scenario_id)
    if not s or s.business_id != ctx.business_id:
        raise HTTPException(404, "Scenario not found")
    snap = db.get(SimulatedSnapshot, s.last_run_state_id) if s.last_run_state_id else None
    dec = db.scalar(select(ScenarioDecision).where(ScenarioDecision.scenario_id == s.id))
    return jsonable({
        "id": s.id, "name": s.name, "kind": s.kind, "description": s.description,
        "parameters": s.parameters_json, "origin": s.origin,
        "created_at": s.created_at.isoformat(),
        "baseline_actual_state_id": s.baseline_actual_state_id,
        "baseline_predicted_state_id": s.baseline_predicted_state_id,
        "outputs": snap.outputs_json if snap else None,
        "decision": {"id": dec.id, "status": dec.status, "note": dec.note,
                     "implementation_date": dec.implementation_date.isoformat()
                                            if dec.implementation_date else None,
                     "outcome": dec.outcome_json} if dec else None,
    })


@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: str, db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    s = db.get(Scenario, scenario_id)
    if not s or s.business_id != ctx.business_id:
        raise HTTPException(404, "Scenario not found")
    s.is_archived = True
    audit(db, ctx, "scenario.archive", entity="scenario", entity_id=s.id)
    db.commit()
    return {"ok": True, "archived": True,
            "note": "Archived, not deleted. Simulated states are kept for the audit trail."}


class DecisionIn(BaseModel):
    status: str
    implementation_date: str | None = None
    note: str = ""


@router.post("/{scenario_id}/decision")
def record_decision(scenario_id: str, body: DecisionIn, db: DbDep, ctx: Tenant):
    """Record what the owner actually decided.

    Marking a scenario 'implemented' records an intention. It does **not**
    create any ledger entry: the realised outcome is measured later from
    verified transactions by ``/evaluate``.
    """
    ctx.require(Role.MANAGER)
    if body.status not in {s.value for s in DecisionStatus}:
        raise HTTPException(422, f"status must be one of {[s.value for s in DecisionStatus]}")
    s = db.get(Scenario, scenario_id)
    if not s or s.business_id != ctx.business_id:
        raise HTTPException(404, "Scenario not found")
    dec = db.scalar(select(ScenarioDecision).where(ScenarioDecision.scenario_id == s.id))
    if dec is None:
        dec = ScenarioDecision(id=_uid(), business_id=ctx.business_id, scenario_id=s.id)
        db.add(dec)
    dec.status = body.status
    dec.decided_by_user_id = ctx.user.id
    dec.decided_at = datetime.now(timezone.utc)
    dec.note = body.note
    if body.implementation_date:
        dec.implementation_date = date.fromisoformat(body.implementation_date)
    audit(db, ctx, "scenario.decision", entity="scenario", entity_id=s.id,
          detail={"status": body.status})
    db.commit()
    return {"ok": True, "scenario_id": s.id, "status": dec.status,
            "note": ("Recorded as a decision only. No ledger entry was created - the "
                     "outcome will be measured from verified transactions.")}


@router.get("/{scenario_id}/evaluate")
def evaluate_decision(scenario_id: str, db: DbDep, ctx: Tenant, as_of: AsOf):
    """Compare an implemented decision against what actually happened."""
    from app.analytics.cash import cash_position
    s = db.get(Scenario, scenario_id)
    if not s or s.business_id != ctx.business_id:
        raise HTTPException(404, "Scenario not found")
    dec = db.scalar(select(ScenarioDecision).where(ScenarioDecision.scenario_id == s.id))
    if not dec or dec.status != DecisionStatus.IMPLEMENTED:
        return {"available": False,
                "reason": ("This scenario has not been marked as implemented, so there "
                           "is no decision to evaluate.")}
    snap = db.get(SimulatedSnapshot, s.last_run_state_id) if s.last_run_state_id else None
    if not snap:
        return {"available": False, "reason": "The scenario has never been run."}
    out = (snap.outputs_json or {}).get("scenario", {})
    starts = out.get("week_starts") or []
    rows = []
    for idx, ws in enumerate(starts):
        d = date.fromisoformat(ws)
        if d > as_of or idx == 0:
            continue
        actual = cash_position(db, ctx.business_id, d)
        act = actual.cash_paise - actual.restricted_paise
        pred = out["p50"][idx]
        rows.append({"week_start": ws, "simulated_p50": money(pred),
                     "actual": money(act), "error": money(act - pred),
                     "within_band": out["p10"][idx] <= act <= out["p90"][idx]})
    if not rows:
        return {"available": False,
                "reason": "No week of the simulated horizon has elapsed yet."}
    mae = sum(abs(r["error"]["paise"]) for r in rows) / len(rows)
    cov = sum(1 for r in rows if r["within_band"]) / len(rows)
    result = {"available": True, "weeks_elapsed": len(rows), "rows": rows,
              "mae": money(int(mae)), "band_coverage": round(cov, 3),
              "lesson": ("The simulation tracked reality well." if cov >= 0.7 else
                         "Reality diverged from the simulation. Review which assumption "
                         "was wrong before relying on a similar scenario again.")}
    dec.outcome_json = jsonable(result)
    db.commit()
    return jsonable(result)
