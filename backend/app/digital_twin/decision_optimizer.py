"""Risk-adjusted comparison of alternative decisions.

Given a set of candidate actions, each is simulated against the same
baseline with the same random draws and then scored on an explicit
objective:

    utility = w_liq * liquidity_gain
            + w_profit * expected_profit
            - w_risk * downside_exposure
            - w_cost * financing_cost

The weights come from the business's risk appetite, and both the weights and
every term are returned. The engine deliberately does **not** present the
top-scoring option as "the answer": it ranks, shows the trade-off, and
leaves the decision with the owner. A mathematically optimal option can
still be commercially wrong for reasons that are not in the ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.digital_twin.scenario_engine import ScenarioError, apply_scenario
from app.forecast.cashflow import ForecastInputs
from app.forecast.monte_carlo import simulate

APPETITE_WEIGHTS = {
    "conservative": {"liquidity": 0.30, "profit": 0.15, "risk": 0.45, "cost": 0.10},
    "balanced":     {"liquidity": 0.30, "profit": 0.30, "risk": 0.28, "cost": 0.12},
    "aggressive":   {"liquidity": 0.20, "profit": 0.48, "risk": 0.18, "cost": 0.14},
}


@dataclass
class Option:
    key: str
    label: str
    kind: str
    params: dict
    note: str = ""


def evaluate(baseline: ForecastInputs, options: list[Option], as_of: date, *,
             risk_appetite: str = "balanced", paths: int = 2000,
             seed: int = 20260101, policies: dict | None = None) -> dict:
    w = APPETITE_WEIGHTS.get(risk_appetite, APPETITE_WEIGHTS["balanced"])
    pol = policies or {}
    base = simulate(baseline, paths=paths, seed=seed)

    rows = []
    for opt in options:
        try:
            fi, extras = apply_scenario(baseline, opt.kind, opt.params, as_of)
            sim = simulate(fi, paths=paths, seed=seed)
        except ScenarioError as e:
            rows.append({"key": opt.key, "label": opt.label, "error": str(e), "feasible": False})
            continue

        liq = sim.min_cash_p50_paise - base.min_cash_p50_paise
        downside = sim.liquidity_cvar_paise - base.liquidity_cvar_paise
        profit = int(extras.get("expected_profit_paise", 0)) + \
                 int(extras.get("in_horizon_saving_paise", 0)) + \
                 int(extras.get("risk_adjusted_uplift_paise", 0))
        cost = int(extras.get("financing_cost_paise", 0) or extras.get("total_cost_paise", 0))

        violations = _check_policies(sim, extras, pol, baseline)
        scale = max(abs(liq), abs(profit), abs(downside), abs(cost), 1)
        utility = (w["liquidity"] * liq / scale + w["profit"] * profit / scale
                   - w["risk"] * downside / scale - w["cost"] * cost / scale)

        rows.append({
            "key": opt.key, "label": opt.label, "kind": opt.kind, "params": opt.params,
            "note": opt.note, "feasible": not violations,
            "policy_violations": violations,
            "utility": round(float(utility), 4),
            "terms": {
                "liquidity_gain_paise": liq, "expected_profit_paise": profit,
                "downside_increase_paise": downside, "financing_cost_paise": cost,
                "normalisation_scale_paise": scale, "weights": w},
            "metrics": {
                "min_cash_p50_paise": sim.min_cash_p50_paise,
                "min_cash_p10_paise": sim.min_cash_p10_paise,
                "closing_cash_p50_paise": sim.p50[-1],
                "runway_weeks_p50": sim.runway_weeks_p50,
                "breach_probability": sim.breach_probability,
                "liquidity_cvar_paise": sim.liquidity_cvar_paise,
                "peak_working_capital_paise": max(0, -min(0, sim.min_cash_p50_paise))},
            "economics": extras,
            "p50_path": sim.p50, "p10_path": sim.p10,
        })

    feasible = [r for r in rows if r.get("feasible")]
    feasible.sort(key=lambda r: -r["utility"])
    for i, r in enumerate(feasible):
        r["rank"] = i + 1
    rows.sort(key=lambda r: (not r.get("feasible", False), -r.get("utility", -99)))

    return {
        "as_of": as_of.isoformat(), "risk_appetite": risk_appetite, "weights": w,
        "seed": seed, "paths": paths,
        "baseline": {"min_cash_p50_paise": base.min_cash_p50_paise,
                     "min_cash_p10_paise": base.min_cash_p10_paise,
                     "closing_cash_p50_paise": base.p50[-1],
                     "runway_weeks_p50": base.runway_weeks_p50,
                     "breach_probability": base.breach_probability,
                     "liquidity_cvar_paise": base.liquidity_cvar_paise,
                     "p50_path": base.p50, "p10_path": base.p10,
                     "week_starts": base.week_starts},
        "options": rows,
        "recommended_key": feasible[0]["key"] if feasible else None,
        "method": ("Every option is simulated against the same baseline with the same "
                   "random draws. Utility is a weighted, normalised trade-off between "
                   "liquidity, profit, downside risk and financing cost."),
        "caveat": ("The highest-utility option is not automatically the right business "
                   "decision. Relationships, strategy and information not in the ledger "
                   "are not modelled. RUNWAY ranks; the owner decides."),
    }


def _check_policies(sim, extras: dict, pol: dict, baseline: ForecastInputs) -> list[str]:
    v = []
    min_cash = pol.get("min_cash_paise", baseline.safety_buffer_paise)
    if sim.min_cash_p10_paise < 0:
        v.append(f"P10 cash goes negative (min {sim.min_cash_p10_paise/100:,.0f})")
    if sim.breach_probability > pol.get("max_breach_probability", 0.40):
        v.append(f"breach probability {sim.breach_probability:.0%} exceeds the "
                 f"{pol.get('max_breach_probability', 0.40):.0%} policy limit")
    rate = extras.get("annual_rate") or extras.get("effective_annualised_rate")
    if rate and rate > pol.get("max_borrowing_apr", 0.24):
        v.append(f"cost of credit {rate:.1%} exceeds the "
                 f"{pol.get('max_borrowing_apr', 0.24):.0%} policy ceiling")
    margin = extras.get("expected_profit_paise")
    rev = extras.get("expected_revenue_paise")
    if margin is not None and rev:
        m = margin / rev
        if m < pol.get("min_order_margin", 0.0):
            v.append(f"order margin {m:.1%} is below the "
                     f"{pol.get('min_order_margin', 0.0):.0%} policy minimum")
    return v
