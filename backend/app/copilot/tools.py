"""The copilot's tool layer.

Every number the copilot can ever say comes from one of these functions.
The language model is not given a calculator, a database handle or the raw
ledger: it is given the JSON these tools return and asked to explain it.

Each tool result carries:
  * ``state`` - actual | predicted | simulated | reconciliation, so the
    answer can always say which of the three states it came from;
  * ``evidence`` - the specific rows or assumptions behind the figures;
  * ``as_of`` - because a financial answer without a date is worthless.

Tools are tenant-bound by construction: they receive a ``TwinBundle`` that
was built for exactly one business, and none of them accepts a business id.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from app.core.money import format_inr

REGISTRY: dict[str, "Tool"] = {}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable
    state: str


def tool(name: str, description: str, state: str, parameters: dict | None = None):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, parameters or {"type": "object",
                                                                "properties": {}}, fn, state)
        return fn
    return deco


def _ok(state: str, summary: str, data: dict, evidence: list, as_of: date) -> dict:
    return {"state": state, "summary": summary, "data": data, "evidence": evidence,
            "as_of": as_of.isoformat(), "ok": True}


def _unavailable(reason: str, as_of: date) -> dict:
    return {"ok": False, "state": "unavailable", "summary": reason, "data": {},
            "evidence": [], "as_of": as_of.isoformat()}


# ───────────────────────── ACTUAL STATE ──────────────────────────────

@tool("get_actual_state", "Current recorded cash, receivables, payables and liquidity.",
      "actual")
def get_actual_state(b, **_) -> dict:
    p, s = b.position, b.actual_snapshot
    return _ok("actual", (
        f"Cash in hand across all accounts is {format_inr(p.cash_paise)}. After "
        f"{format_inr(p.restricted_paise)} restricted and {format_inr(p.committed_paise)} "
        f"committed, available operating liquidity is "
        f"{format_inr(p.available_liquidity_paise)}."), {
        "cash_paise": p.cash_paise, "restricted_paise": p.restricted_paise,
        "committed_paise": p.committed_paise,
        "available_liquidity_paise": p.available_liquidity_paise,
        "overdraft_headroom_paise": p.overdraft_headroom_paise,
        "receivables_paise": s.receivables_paise,
        "receivables_overdue_paise": s.receivables_overdue_paise,
        "payables_paise": s.payables_paise,
        "payables_overdue_paise": s.payables_overdue_paise,
        "working_capital_paise": s.working_capital_paise,
        "revenue_30d_paise": s.revenue_30d_paise,
        "expense_30d_paise": s.expense_30d_paise,
        "accounts": p.accounts,
        "state_version": b.actual_state.version,
        "data_quality_score": b.data_quality["score"],
    }, [{"label": a["name"], "value": format_inr(a["closing_paise"])} for a in p.accounts]
       + [{"label": "Data quality", "value": f"{b.data_quality['score']}/100 "
                                             f"({b.data_quality['band']})"}], b.as_of)


@tool("get_cash_position", "Cash broken into restricted, committed and available.", "actual")
def get_cash_position(b, **_) -> dict:
    return get_actual_state(b)


@tool("get_receivables", "Open receivables with ageing and the prioritised collection list.",
      "actual")
def get_receivables(b, limit: int = 8, **_) -> dict:
    a = b.ageing_ar
    rows = b.collection_list[:limit]
    return _ok("actual", (
        f"{format_inr(a['total_paise'])} is outstanding from customers, of which "
        f"{format_inr(a['overdue_paise'])} ({a['overdue_share']:.0%}) is past due."), {
        "ageing": a, "collection_list": rows,
        "total_paise": a["total_paise"], "overdue_paise": a["overdue_paise"],
    }, [{"label": f"{r['customer']} {r['invoice_no']}",
         "value": f"{format_inr(r['outstanding_paise'])}, {r['days_past_due']} days past due, "
                  f"predicted {r['predicted_pay_date']}"} for r in rows], b.as_of)


@tool("get_payables", "Supplier obligations, payment calendar and MSMED exposure.", "actual")
def get_payables(b, **_) -> dict:
    return _ok("actual", (
        f"{format_inr(b.ageing_ap['total_paise'])} is payable to suppliers. "
        f"{format_inr(b.msmed['covered_outstanding_paise'])} of that is owed to micro or "
        f"small enterprises covered by the MSMED 45/15-day rule."), {
        "ageing": b.ageing_ap, "calendar": b.payment_calendar[:6], "msmed": b.msmed,
        "suppliers": [s.dict() for s in b.supplier_profiles[:10]],
    }, [{"label": w["week_start"], "value": format_inr(w["amount_paise"])}
        for w in b.payment_calendar[:6]], b.as_of)


@tool("get_customer_risk", "Payment behaviour and risk band for each customer.", "actual")
def get_customer_risk(b, customer: str | None = None, **_) -> dict:
    rows = b.behaviour
    if customer:
        q = customer.lower()
        hit = [c for c in rows if q in c.name.lower()]
        if not hit:
            return _unavailable(
                f"No customer matching '{customer}' exists in this workspace. "
                f"Known customers: " + ", ".join(c.name for c in rows[:8]), b.as_of)
        rows = hit
    return _ok("actual", (
        f"{rows[0].name} pays on average {rows[0].mean_delay_days:+.0f} days against terms "
        f"with {format_inr(rows[0].outstanding_paise)} outstanding "
        f"({rows[0].risk_band} risk)." if len(rows) == 1 else
        f"{len(rows)} customers analysed; "
        f"{sum(1 for c in rows if c.risk_band in ('high', 'critical'))} are high or "
        f"critical risk."), {
        "customers": [c.dict() for c in rows],
    }, [{"label": c.name,
         "value": f"mean {c.mean_delay_days:+.1f}d, reliability {c.reliability_score}/100, "
                  f"{format_inr(c.outstanding_paise)} open, {c.risk_band} risk "
                  f"({c.invoices_settled} settled invoices analysed)"} for c in rows[:8]],
        b.as_of)


@tool("get_supplier_obligations", "Upcoming supplier payments and statutory deadlines.",
      "actual")
def get_supplier_obligations(b, **_) -> dict:
    return get_payables(b)


@tool("get_upcoming_liabilities", "The obligation calendar: GST, payroll, rent, EMIs.",
      "actual")
def get_upcoming_liabilities(b, days: int = 45, **_) -> dict:
    items = [i for i in b.obligations["items"] if i["days_away"] <= days]
    total = sum(i["amount_paise"] for i in items if not i["overdue"])
    return _ok("actual", (
        f"{format_inr(total)} falls due in the next {days} days across {len(items)} items, "
        f"including {format_inr(b.obligations['statutory_paise'])} of statutory dues. "
        f"Liquidity plus expected collections covers this "
        f"{b.coverage['coverage_ratio']:.2f} times."), {
        "items": items, "total_paise": total, "coverage": b.coverage,
    }, [{"label": i["label"],
         "value": f"{format_inr(i['amount_paise'])} in {i['days_away']} days"
                  + (" (RUNWAY estimate)" if i["is_estimated"] else "")} for i in items[:10]],
        b.as_of)


@tool("get_transactions_summary", "Recent cash movement by category.", "actual")
def get_transactions_summary(b, **_) -> dict:
    f = b.flow_30d
    return _ok("actual", (
        f"Over the last 30 days {format_inr(f['inflow_paise'])} came in and "
        f"{format_inr(f['outflow_paise'])} went out, a net of {format_inr(f['net_paise'])}."),
        {"flow": f, "working_capital": b.working_capital},
        [{"label": c["category"].replace("_", " ").title(),
          "value": f"in {format_inr(c['inflow_paise'])}, out {format_inr(c['outflow_paise'])} "
                   f"({c['count']} transactions)"} for c in f["by_category"][:8]], b.as_of)


# ──────────────────────── PREDICTED STATE ────────────────────────────

@tool("get_predicted_state", "The 13-week cash forecast with P10/P50/P90 bands.", "predicted")
def get_predicted_state(b, **_) -> dict:
    s = b.simulation
    if not s:
        return _unavailable("No forecast has been generated for this business yet.", b.as_of)
    return _ok("predicted", (
        f"The median path ends week {s.horizon_weeks} at {format_inr(s.p50[-1])}. "
        f"The lowest point on the median path is {format_inr(s.min_cash_p50_paise)}; "
        f"on the pessimistic P10 path it is {format_inr(s.min_cash_p10_paise)}. "
        f"Across {s.paths:,} simulated paths, {s.breach_probability:.0%} fall below the "
        f"{format_inr(s.safety_buffer_paise)} safety buffer at some point."), {
        "week_starts": s.week_starts, "p10": s.p10, "p50": s.p50, "p90": s.p90,
        "runway_weeks_p10": s.runway_weeks_p10, "runway_weeks_p50": s.runway_weeks_p50,
        "min_cash_p10_paise": s.min_cash_p10_paise, "min_cash_p50_paise": s.min_cash_p50_paise,
        "breach_probability": s.breach_probability,
        "breach_prob_by_week": s.breach_prob_by_week,
        "first_breach_week": s.first_breach_week_p50,
        "liquidity_var_paise": s.liquidity_var_paise,
        "liquidity_cvar_paise": s.liquidity_cvar_paise,
        "drivers": s.drivers, "paths": s.paths, "seed": s.seed,
        "model_version": b.predicted_snapshot.model_version,
        "state_version": b.predicted_state.version,
    }, [{"label": d["driver"], "value": f"{d['direction']} {format_inr(d['amount_paise'])} "
                                        f"({d['evidence']})"} for d in s.drivers[:7]], b.as_of)


@tool("get_cash_runway", "How long the business can operate before breaching its buffer.",
      "predicted")
def get_cash_runway(b, **_) -> dict:
    s = b.simulation
    if not s:
        return _unavailable("No forecast available.", b.as_of)
    censored = s.runway_weeks_p50 >= s.horizon_weeks
    return _ok("predicted", (
        f"Median runway is {'beyond the ' + str(s.horizon_weeks) + '-week horizon' if censored else f'{s.runway_weeks_p50} weeks'}"
        f", but the pessimistic P10 path breaches the buffer after "
        f"{s.runway_weeks_p10} weeks."), {
        "runway_weeks_p10": s.runway_weeks_p10, "runway_weeks_p50": s.runway_weeks_p50,
        "runway_weeks_p90": s.runway_weeks_p90, "horizon_weeks": s.horizon_weeks,
        "censored": censored, "safety_buffer_paise": s.safety_buffer_paise,
        "breach_probability": s.breach_probability,
        "first_breach_week": s.first_breach_week_p50,
    }, [{"label": "Runway P10 / P50 / P90",
         "value": f"{s.runway_weeks_p10} / {s.runway_weeks_p50} / {s.runway_weeks_p90} weeks"},
        {"label": "Censoring", "value": "A runway equal to the horizon means 'beyond the "
                                        "forecast window', not exactly that many weeks."}],
        b.as_of)


@tool("get_forecast_drivers", "What is actually moving the forecast.", "predicted")
def get_forecast_drivers(b, **_) -> dict:
    if not b.simulation:
        return _unavailable("No forecast available.", b.as_of)
    return _ok("predicted", "The forecast is driven by these components, largest first.",
               {"drivers": b.simulation.drivers,
                "assumptions": b.simulation.assumptions,
                "sensitivity": b.sensitivity},
               [{"label": d["driver"],
                 "value": f"{d['direction']} {format_inr(d['amount_paise'])} - {d['evidence']}"}
                for d in b.simulation.drivers], b.as_of)


@tool("get_payment_prediction", "Predicted payment date for a specific invoice or customer.",
      "predicted")
def get_payment_prediction(b, invoice_no: str | None = None,
                           customer: str | None = None, **_) -> dict:
    rows = b.collection_list
    if invoice_no:
        rows = [r for r in rows if invoice_no.upper() in r["invoice_no"].upper()]
    if customer:
        rows = [r for r in rows if customer.lower() in r["customer"].lower()]
    if not rows:
        return _unavailable(
            "No open invoice matches that description. RUNWAY will not estimate a payment "
            "date for an invoice it cannot find.", b.as_of)
    top = rows[0]
    pred = b.predictions.get(top["invoice_id"], {})
    return _ok("predicted", (
        f"{top['invoice_no']} from {top['customer']} ({format_inr(top['outstanding_paise'])}) "
        f"was due {top['due_date']} and is predicted to be paid around "
        f"{top['predicted_pay_date']}."), {
        "invoices": rows[:10], "detail": pred,
    }, ([{"label": "Probability within 15 days",
          "value": f"{(top.get('prob_within_15') or 0):.0%}"},
         {"label": "Customer reliability", "value": f"{top.get('reliability_score')}/100"}]
        + [{"label": d["feature"], "value": f"{d['contribution_days']:+.1f} days"}
           for d in (pred.get("drivers") or [])[:5]]), b.as_of)


@tool("get_risk_alerts", "Open risk alerts with evidence and recommended action.", "predicted")
def get_risk_alerts(b, level: str | None = None, **_) -> dict:
    rows = b.findings
    if level:
        rows = [f for f in rows if f.level == level]
    return _ok("predicted", (
        f"{len(rows)} open alerts: "
        + ", ".join(f"{sum(1 for f in rows if f.level == l)} {l}"
                    for l in ("critical", "warning", "watch", "info")
                    if any(f.level == l for f in rows)) or "none"), {
        "alerts": [{"code": f.code, "level": f.level, "title": f.title,
                    "what_happened": f.what_happened, "why_it_matters": f.why_it_matters,
                    "evidence": f.evidence, "impact_paise": f.impact_paise,
                    "recommended_action": f.recommended_action,
                    "if_ignored": f.if_ignored} for f in rows],
    }, [{"label": f.level.upper(), "value": f.title} for f in rows[:8]], b.as_of)


@tool("get_financial_health", "The 0-100 health score and its eight dimensions.", "predicted")
def get_financial_health(b, **_) -> dict:
    h = b.health
    weakest = min(h["subscores"], key=lambda s: s["score"])
    return _ok("predicted", (
        f"Financial health is {h['score']}/100 ({h['band']}). The weakest dimension is "
        f"{weakest['label'].lower()} at {weakest['score']}."), h,
        [{"label": s["label"], "value": f"{s['score']}/100 ({s['band']}), weight {s['weight']:.0%}"}
         for s in h["subscores"]], b.as_of)


@tool("get_recommendations", "Ranked, evidence-backed actions.", "predicted")
def get_recommendations(b, limit: int = 6, **_) -> dict:
    rows = b.recommendations[:limit]
    return _ok("predicted", f"{len(b.recommendations)} recommendations, highest priority first.",
               {"recommendations": [{
                   "code": r.code, "title": r.title, "priority": r.priority,
                   "score_terms": r.score_terms, "evidence": r.trigger_evidence,
                   "expected_effect_paise": r.expected_effect_paise,
                   "expected_effect_text": r.expected_effect_text,
                   "downside": r.downside_text, "action": r.required_action,
                   "deadline": r.deadline.isoformat() if r.deadline else None,
                   "confidence": r.confidence, "explanation": r.explanation,
                   "requires_approval": r.requires_approval,
                   "linked_scenario": r.linked_scenario} for r in rows]},
               [{"label": f"P{r.priority}", "value": r.title} for r in rows], b.as_of)


@tool("get_stress_tests", "How the business fares under predefined shocks.", "predicted")
def get_stress_tests(b, **_) -> dict:
    if not b.stress:
        return _unavailable("Stress tests have not been computed for this request.", b.as_of)
    failing = [s for s in b.stress if not s["survives_with_overdraft"]]
    return _ok("predicted", (
        f"{len(b.stress)} stress tests run. The business does not survive "
        f"{len(failing)} of them even after drawing the overdraft."),
        {"tests": b.stress},
        [{"label": s["label"],
          "value": f"min cash P10 {format_inr(s['min_cash_p10_paise'])}, "
                   f"runway {s['runway_weeks_p50']}w, "
                   f"{'survives' if s['survives_with_overdraft'] else 'DOES NOT SURVIVE'}"}
         for s in b.stress], b.as_of)


@tool("get_concentration_risk", "Customer and supplier concentration.", "predicted")
def get_concentration_risk(b, **_) -> dict:
    c = b.concentration
    return _ok("predicted", c["interpretation"],
               {"concentration": c, "correlation": b.correlation},
               [{"label": t["name"], "value": f"{t['share']:.0%} of revenue, "
                                              f"{format_inr(t['outstanding_paise'])} open"}
                for t in c["top_counterparties"][:6]], b.as_of)


@tool("evaluate_forecast_accuracy", "How accurate past forecasts turned out to be.",
      "reconciliation")
def evaluate_forecast_accuracy(b, db=None, **_) -> dict:
    from app.financial_states.state_manager import reconcile_forecasts
    if db is None:
        return _unavailable("Accuracy evaluation needs a database session.", b.as_of)
    r = reconcile_forecasts(db, b.business.id, b.as_of)
    db.commit()
    if not r["available"]:
        return _unavailable(
            "No forecast has reached its target week yet, so there is nothing to score. "
            "RUNWAY will not quote an accuracy figure it has not measured.", b.as_of)
    return _ok("reconciliation", "Measured accuracy of past forecasts against actuals.", r,
               [{"label": f"{h['horizon_weeks']}-week horizon",
                 "value": f"MAE {format_inr(h['mae_paise'])}, WAPE {h['wape']:.1%}, "
                          f"P10-P90 coverage {h['p10_p90_coverage']:.0%} (target 80%)"}
                for h in r["cash_forecast_by_horizon"]], b.as_of)


@tool("get_data_quality", "How complete and fresh the underlying data is.", "actual")
def get_data_quality(b, **_) -> dict:
    q = b.data_quality
    return _ok("actual", (
        f"Data quality is {q['score']}/100 ({q['band']}). " +
        (" ".join(q["warnings"]) if q["warnings"] else "No data-quality warnings.")), q,
        [{"label": "Verified share", "value": f"{q['verified_share']:.0%}"},
         {"label": "Reconciled share", "value": f"{q['reconciled_share']:.0%}"},
         {"label": "Last transaction", "value": q["last_transaction_date"] or "none"}],
        b.as_of)


# ──────────────────────── SIMULATED STATE ────────────────────────────

@tool("run_scenario", "Simulate a decision and compare it against the baseline.", "simulated")
def run_scenario_tool(b, db=None, kind: str | None = None, params: dict | None = None, **_) -> dict:
    from app.digital_twin.scenario_engine import ScenarioError, apply_scenario
    from app.financial_states.state_manager import compare_simulations
    from app.forecast.monte_carlo import simulate
    from app.core.config import settings as _s

    if not kind:
        return _unavailable("A scenario needs a kind. Ask for one of the catalogue types.",
                            b.as_of)
    try:
        fi, extras = apply_scenario(b.forecast_inputs, kind, params or {}, b.as_of)
    except ScenarioError as e:
        return _unavailable(f"That scenario cannot be built: {e}", b.as_of)
    base = simulate(b.forecast_inputs, paths=2000, seed=_s.monte_carlo_seed)
    scen = simulate(fi, paths=2000, seed=_s.monte_carlo_seed)
    cmp = compare_simulations(base, scen, extras)
    return _ok("simulated", (
        f"{extras.get('narrative', kind)} Runway moves from {base.runway_weeks_p50} to "
        f"{scen.runway_weeks_p50} weeks and minimum cash from "
        f"{format_inr(base.min_cash_p50_paise)} to {format_inr(scen.min_cash_p50_paise)}."),
        {"comparison": cmp, "economics": extras, "kind": kind, "params": params or {}},
        [{"label": r["metric"],
          "value": f"{r['baseline']} -> {r['scenario']} ({r['direction']})"}
         for r in cmp["rows"]], b.as_of)


@tool("compare_options", "Rank several alternative decisions on a risk-adjusted basis.",
      "simulated")
def compare_options(b, options: list | None = None, **_) -> dict:
    from app.digital_twin.decision_optimizer import Option, evaluate
    if not options:
        return _unavailable("No options supplied to compare.", b.as_of)
    opts = [Option(key=o.get("key", f"opt{i}"), label=o.get("label", f"Option {i+1}"),
                   kind=o["kind"], params=o.get("params", {}), note=o.get("note", ""))
            for i, o in enumerate(options)]
    res = evaluate(b.forecast_inputs, opts, b.as_of,
                   risk_appetite=b.business.risk_appetite,
                   policies={"min_cash_paise": b.business.safety_buffer_paise,
                             "max_borrowing_apr": b.business.max_borrowing_apr,
                             "min_order_margin": b.business.min_order_margin})
    best = next((o for o in res["options"] if o.get("rank") == 1), None)
    return _ok("simulated",
               (f"{len(opts)} options compared. '{best['label']}' ranks highest on the "
                f"{res['risk_appetite']} objective." if best else
                "No option satisfies the business's policy constraints."),
               res, [{"label": o["label"],
                      "value": (f"utility {o['utility']:+.3f}, min cash "
                                f"{format_inr(o['metrics']['min_cash_p50_paise'])}, "
                                f"runway {o['metrics']['runway_weeks_p50']}w"
                                if o.get("feasible") else
                                f"not feasible: {'; '.join(o.get('policy_violations', []))}")}
                     for o in res["options"]], b.as_of)


@tool("get_scenario_catalogue", "What kinds of scenario can be simulated.", "simulated")
def get_scenario_catalogue(b, **_) -> dict:
    from app.digital_twin.scenario_engine import CATALOGUE
    return _ok("simulated", f"{len(CATALOGUE)} scenario types are available.",
               {"catalogue": CATALOGUE},
               [{"label": c["label"], "value": c["question"]} for c in CATALOGUE], b.as_of)


def call(name: str, bundle, db=None, **kwargs) -> dict:
    t = REGISTRY.get(name)
    if t is None:
        return {"ok": False, "state": "unavailable",
                "summary": f"Unknown tool '{name}'.", "data": {}, "evidence": [],
                "as_of": bundle.as_of.isoformat()}
    try:
        return t.fn(bundle, db=db, **kwargs)
    except TypeError:
        return t.fn(bundle, **kwargs)


def schema() -> list[dict]:
    return [{"name": t.name, "description": t.description, "state": t.state,
             "input_schema": t.parameters} for t in REGISTRY.values()]
