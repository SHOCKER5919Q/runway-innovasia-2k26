"""Predefined stress tests.

Each test is a named mutation of ``ForecastInputs`` re-simulated under
**common random numbers** against the baseline, so the reported delta is
caused by the stress and not by sampling noise.

These are deliberately severe but plausible. They answer "could this business
survive X?", not "will X happen?".
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.forecast.cashflow import ForecastInputs
from app.forecast.monte_carlo import SimulationResult, simulate


@dataclass
class StressTest:
    key: str
    label: str
    description: str
    severity: str          # moderate | severe | extreme
    apply: callable


def _delay_all(days: float):
    def f(fi: ForecastInputs):
        for i in fi.inflows:
            i.day_offset += days
        fi.new_sales_collection_lag_days += days
    return f


def _largest_customer_default(fi: ForecastInputs):
    if not fi.inflows:
        return
    by_cp: dict[str, int] = {}
    for i in fi.inflows:
        by_cp[i.counterparty_id] = by_cp.get(i.counterparty_id, 0) + i.amount_paise
    worst = max(by_cp, key=by_cp.get)
    fi.inflows = [i for i in fi.inflows if i.counterparty_id != worst]
    fi.assumptions["stress_removed_counterparty"] = worst
    fi.assumptions["stress_removed_paise"] = by_cp[worst]


def _revenue_drop(pct: float):
    def f(fi: ForecastInputs):
        fi.weekly_new_sales_paise = [int(v * (1 - pct)) for v in fi.weekly_new_sales_paise]
    return f


def _cost_rise(pct: float):
    def f(fi: ForecastInputs):
        fi.cogs_ratio = min(1.3, fi.cogs_ratio * (1 + pct))
        for o in fi.outflows:
            if o.kind == "supplier_invoice":
                o.amount_paise = int(o.amount_paise * (1 + pct * 0.4))
    return f


def _correlated_squeeze(fi: ForecastInputs):
    """Everybody pays late together - the single-factor correlation turned up."""
    fi.delay_correlation = 0.75
    for i in fi.inflows:
        i.sigma_days *= 1.4


def _compound(*fns):
    def f(fi: ForecastInputs):
        for fn in fns:
            fn(fi)
    return f


TESTS: list[StressTest] = [
    StressTest("largest_customer_default", "Largest customer defaults",
               "The counterparty with the biggest open exposure pays nothing in the horizon.",
               "extreme", _largest_customer_default),
    StressTest("receivables_delay_30", "All receivables 30 days later",
               "Every open invoice and every future collection slips by 30 days.",
               "severe", _delay_all(30)),
    StressTest("receivables_delay_15", "All receivables 15 days later",
               "A market-wide payment slowdown of two weeks.",
               "moderate", _delay_all(15)),
    StressTest("revenue_drop_20", "Revenue falls 20%",
               "Sales not yet invoiced come in a fifth below the run-rate.",
               "severe", _revenue_drop(0.20)),
    StressTest("cost_rise_15", "Input costs rise 15%",
               "Purchase prices and open supplier bills increase.",
               "moderate", _cost_rise(0.15)),
    StressTest("seasonal_weakness", "Festive demand does not materialise",
               "Revenue 12% below run-rate with collections 10 days slower.",
               "moderate", _compound(_revenue_drop(0.12), _delay_all(10))),
    StressTest("correlated_squeeze", "Market-wide payment squeeze",
               "Customer delays become highly correlated (rho 0.75) and more volatile.",
               "severe", _correlated_squeeze),
    StressTest("compound_shock", "Compound shock",
               "Revenue falls 20%, costs rise 15% and collections slip 20 days at once.",
               "extreme", _compound(_revenue_drop(0.20), _cost_rise(0.15), _delay_all(20))),
]


def run_all(fi: ForecastInputs, baseline: SimulationResult, *,
            paths: int = 2000, seed: int = 20260101) -> list[dict]:
    out = []
    for t in TESTS:
        f = fi.copy()
        t.apply(f)
        r = simulate(f, paths=paths, seed=seed)       # common random numbers
        out.append({
            "key": t.key, "label": t.label, "description": t.description,
            "severity": t.severity,
            "min_cash_p50_paise": r.min_cash_p50_paise,
            "min_cash_p10_paise": r.min_cash_p10_paise,
            "min_cash_delta_paise": r.min_cash_p50_paise - baseline.min_cash_p50_paise,
            "runway_weeks_p50": r.runway_weeks_p50,
            "runway_delta_weeks": round(r.runway_weeks_p50 - baseline.runway_weeks_p50, 2),
            "breach_probability": r.breach_probability,
            "breach_delta": round(r.breach_probability - baseline.breach_probability, 4),
            "negative_cash_probability": r.negative_cash_probability,
            "liquidity_var_paise": r.liquidity_var_paise,
            "liquidity_cvar_paise": r.liquidity_cvar_paise,
            "survives": bool(r.min_cash_p10_paise >= 0),
            "survives_with_overdraft": bool(
                r.min_cash_p10_paise + fi.overdraft_limit_paise >= 0),
            "p50_path": r.p50, "p10_path": r.p10,
            "extra": {k: v for k, v in f.assumptions.items() if k.startswith("stress_")},
        })
    out.sort(key=lambda r: r["min_cash_delta_paise"])
    return out
