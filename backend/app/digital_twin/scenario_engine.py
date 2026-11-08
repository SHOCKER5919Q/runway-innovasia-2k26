"""The deterministic scenario engine.

A scenario is a **named, parameterised mutation of ``ForecastInputs``**.
That single design decision is what makes the whole three-state architecture
hold together:

* the baseline and every branch are evaluated by the *same* simulator, so a
  comparison is apples-to-apples by construction;
* nothing a scenario does can touch the ledger - it only edits an in-memory
  copy of the forecast inputs, so scenario isolation is structural rather
  than a rule someone has to remember;
* re-running a saved scenario with the same baseline and seed reproduces the
  result exactly.

Each handler also returns ``extras``: the economics that are not visible in
the cash path alone (expected profit, financing cost, peak working capital).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from app.core.enums import ScenarioKind
from app.core.money import format_inr
from app.forecast.cashflow import ForecastInputs, ScheduledInflow, ScheduledOutflow


class ScenarioError(ValueError):
    pass


@dataclass
class ParamSpec:
    key: str
    label: str
    kind: str          # money | days | percent | int | text | select
    default: Any
    min: float | None = None
    max: float | None = None
    help: str = ""
    options: list[dict] | None = None


@dataclass
class ScenarioType:
    kind: str
    label: str
    question: str
    description: str
    params: list[ParamSpec]
    handler: Callable[[ForecastInputs, dict, date], dict]


def _p(fi: ForecastInputs, params: dict, key: str, spec_default=None):
    v = params.get(key, spec_default)
    if v is None:
        raise ScenarioError(f"missing scenario parameter '{key}'")
    return v


def _amortised_emi(principal: int, annual_rate: float, months: int) -> int:
    if months <= 0:
        return principal
    r = annual_rate / 12.0
    if r <= 0:
        return principal // months
    f = (1 + r) ** months
    return int(round(principal * r * f / (f - 1)))


def _add_monthly(fi: ForecastInputs, label: str, kind: str, amount: int,
                 start_days: int, months: int) -> None:
    for k in range(months):
        off = start_days + 30 * k
        if off > fi.horizon_weeks * 7:
            break
        fi.outflows.append(ScheduledOutflow(
            label=f"{label} ({k+1}/{months})", kind=kind, amount_paise=amount,
            day_offset=float(off), sigma_days=1.0, flexible=False))


# ───────────────────────────── handlers ──────────────────────────────

def h_new_order(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    """Accept a new customer order.

    Models the full working-capital cycle, not just the profit:
      advance in -> materials bought and paid -> goods delivered ->
      balance collected after the credit period.
    """
    value = int(_p(fi, p, "order_value_paise"))
    margin = float(p.get("margin_pct", 0.18))
    advance = float(p.get("advance_pct", 0.0))
    credit_days = int(p.get("credit_days", 60))
    start_in = int(p.get("start_in_days", 7))
    production_days = int(p.get("production_days", 21))
    supplier_credit = int(p.get("supplier_credit_days", 30))
    material_share = float(p.get("material_cost_pct", 1 - margin))
    collection_sigma = float(p.get("collection_sigma_days", 12))

    material_cost = int(value * material_share)
    advance_amt = int(value * advance)
    balance = value - advance_amt

    if advance_amt > 0:
        fi.inflows.append(ScheduledInflow(
            invoice_id=f"scn-advance", counterparty_id="scn-new-customer",
            amount_paise=advance_amt, day_offset=float(start_in), sigma_days=3.0,
            label=f"Advance {advance:.0%} on new order"))
    # Materials are ordered at the start and paid on the supplier's terms.
    fi.outflows.append(ScheduledOutflow(
        label="Materials for new order", kind="supplier_invoice",
        amount_paise=material_cost, day_offset=float(start_in + supplier_credit),
        sigma_days=2.0, flexible=False))
    delivery = start_in + production_days
    fi.inflows.append(ScheduledInflow(
        invoice_id="scn-balance", counterparty_id="scn-new-customer",
        amount_paise=balance, day_offset=float(delivery + credit_days),
        sigma_days=collection_sigma, label="Balance on new order"))

    peak_need = max(0, material_cost - advance_amt)
    return {
        "expected_revenue_paise": value,
        "expected_profit_paise": value - material_cost,
        "material_cost_paise": material_cost,
        "advance_paise": advance_amt,
        "cash_out_before_cash_in_paise": peak_need,
        "funding_gap_days": max(0, (delivery + credit_days) - (start_in + supplier_credit)),
        "collection_day_offset": delivery + credit_days,
        "narrative": (
            f"{format_inr(int(value))} order at {margin:.0%} margin. {format_inr(int(material_cost))} "
            f"of materials is payable on day {start_in + supplier_credit}, while the "
            f"{format_inr(int(balance))} balance arrives on day {delivery + credit_days} - a "
            f"{max(0, (delivery + credit_days) - (start_in + supplier_credit))}-day funding gap "
            f"of up to {format_inr(int(peak_need))}."),
    }


def h_payment_delay(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    days = float(_p(fi, p, "delay_days", 30))
    target = p.get("counterparty_id") or "largest"
    if target == "largest":
        by_cp: dict[str, int] = {}
        for i in fi.inflows:
            by_cp[i.counterparty_id] = by_cp.get(i.counterparty_id, 0) + i.amount_paise
        target = max(by_cp, key=by_cp.get) if by_cp else None
    affected, amount = 0, 0
    for i in fi.inflows:
        if target in (None, "all") or i.counterparty_id == target:
            i.day_offset += days
            affected += 1
            amount += i.amount_paise
    if target in (None, "all"):
        fi.new_sales_collection_lag_days += days
    return {"affected_invoices": affected, "affected_amount_paise": amount,
            "delay_days": days, "counterparty_id": target,
            "narrative": (f"{affected} open invoices worth {format_inr(int(amount))} pushed "
                          f"{days:.0f} days later.")}


def h_customer_default(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    target = p.get("counterparty_id") or "largest"
    recovery = float(p.get("recovery_pct", 0.0))
    if target == "largest":
        by_cp: dict[str, int] = {}
        for i in fi.inflows:
            by_cp[i.counterparty_id] = by_cp.get(i.counterparty_id, 0) + i.amount_paise
        target = max(by_cp, key=by_cp.get) if by_cp else None
    lost = 0
    kept: list[ScheduledInflow] = []
    for i in fi.inflows:
        if i.counterparty_id == target:
            lost += i.amount_paise
            if recovery > 0:
                i.amount_paise = int(i.amount_paise * recovery)
                i.day_offset += 90
                kept.append(i)
        else:
            kept.append(i)
    fi.inflows = kept
    return {"counterparty_id": target, "written_off_paise": int(lost * (1 - recovery)),
            "recovery_pct": recovery,
            "narrative": (f"{format_inr(int(lost))} of open exposure, of which "
                          f"{format_inr(int(lost*(1-recovery)))} is assumed unrecoverable.")}


def h_revenue_shock(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    pct = float(_p(fi, p, "drop_pct", 0.20))
    before = sum(fi.weekly_new_sales_paise)
    fi.weekly_new_sales_paise = [int(v * (1 - pct)) for v in fi.weekly_new_sales_paise]
    after = sum(fi.weekly_new_sales_paise)
    return {"drop_pct": pct, "revenue_reduction_paise": before - after,
            "narrative": f"Forecast sales cut {pct:.0%}, Rs {(before-after)/100:,.0f} over the horizon."}


def h_cost_increase(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    pct = float(_p(fi, p, "increase_pct", 0.10))
    scope = p.get("scope", "materials")
    extra = 0
    if scope in ("materials", "both"):
        base = sum(fi.weekly_new_sales_paise) * fi.cogs_ratio
        fi.cogs_ratio = min(1.3, fi.cogs_ratio * (1 + pct))
        extra += int(sum(fi.weekly_new_sales_paise) * fi.cogs_ratio - base)
    if scope in ("open_bills", "both"):
        for o in fi.outflows:
            if o.kind == "supplier_invoice":
                add = int(o.amount_paise * pct)
                o.amount_paise += add
                extra += add
    return {"increase_pct": pct, "scope": scope, "extra_cost_paise": extra,
            "narrative": f"Input costs up {pct:.0%}, {format_inr(int(extra))} extra over the horizon."}


def h_hiring(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    heads = int(_p(fi, p, "headcount", 2))
    monthly = int(_p(fi, p, "monthly_cost_per_head_paise", 35_000_00))
    start_in = int(p.get("start_in_days", 30))
    uplift = int(p.get("expected_monthly_revenue_uplift_paise", 0))
    uplift_prob = float(p.get("uplift_probability", 0.5))
    ramp_months = int(p.get("uplift_ramp_months", 3))
    months = max(1, (fi.horizon_weeks * 7 - start_in) // 30 + 1)
    cost = heads * monthly
    _add_monthly(fi, f"Payroll for {heads} new hires", "payroll", cost, start_in, months)
    # The benefit is explicitly uncertain and explicitly risk-adjusted, rather
    # than being assumed into existence.
    realised = 0
    if uplift > 0:
        for k in range(months):
            if k < ramp_months - 1:
                continue
            off = start_in + 30 * k + int(fi.new_sales_collection_lag_days)
            if off > fi.horizon_weeks * 7:
                break
            amt = int(uplift * uplift_prob)
            realised += amt
            fi.inflows.append(ScheduledInflow(
                invoice_id=f"scn-hire-uplift-{k}", counterparty_id="scn-hiring-uplift",
                amount_paise=amt, day_offset=float(off), sigma_days=18.0,
                label="Revenue uplift from new hires (risk-adjusted)"))
    return {"headcount": heads, "monthly_cost_paise": cost,
            "total_cost_paise": cost * months,
            "risk_adjusted_uplift_paise": realised,
            "uplift_probability": uplift_prob,
            "narrative": (f"{heads} hires at {format_inr(int(cost))} a month. Any revenue benefit is "
                          f"applied at {uplift_prob:.0%} probability and only from month "
                          f"{ramp_months}, because a new hire does not pay for themselves "
                          f"on day one.")}


def h_equipment(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    cost = int(_p(fi, p, "cost_paise"))
    down_pct = float(p.get("down_payment_pct", 0.25))
    rate = float(p.get("annual_rate", 0.135))
    tenure = int(p.get("tenure_months", 36))
    start_in = int(p.get("start_in_days", 14))
    saving = int(p.get("monthly_saving_paise", 0))
    maintenance = int(p.get("monthly_maintenance_paise", 0))
    down = int(cost * down_pct)
    financed = cost - down
    emi = _amortised_emi(financed, rate, tenure) if financed > 0 else 0

    fi.outflows.append(ScheduledOutflow(
        label="Equipment down payment", kind="capex", amount_paise=down,
        day_offset=float(start_in), sigma_days=1.0, flexible=True))
    months = max(1, (fi.horizon_weeks * 7 - start_in) // 30 + 1)
    if emi:
        _add_monthly(fi, "Equipment loan EMI", "loan_emi", emi, start_in + 30, months)
    if maintenance:
        _add_monthly(fi, "Equipment maintenance", "other", maintenance, start_in + 30, months)
    net_saving = 0
    if saving:
        for k in range(months):
            off = start_in + 30 * (k + 1)
            if off > fi.horizon_weeks * 7:
                break
            net_saving += saving
            fi.inflows.append(ScheduledInflow(
                invoice_id=f"scn-saving-{k}", counterparty_id="scn-equipment-saving",
                amount_paise=saving, day_offset=float(off), sigma_days=5.0,
                label="Operational saving from equipment"))
    total_interest = emi * tenure - financed if emi else 0
    return {"cost_paise": cost, "down_payment_paise": down, "financed_paise": financed,
            "emi_paise": emi, "tenure_months": tenure,
            "total_interest_paise": total_interest,
            "in_horizon_saving_paise": net_saving,
            "narrative": (f"{format_inr(int(cost))} equipment: {format_inr(int(down))} down and "
                          f"{format_inr(int(emi))} a month for {tenure} months. Total interest over "
                          f"the full term is {format_inr(int(total_interest))}.")}


def h_financing(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    amount = int(_p(fi, p, "amount_paise"))
    rate = float(p.get("annual_rate", 0.16))
    tenure = int(p.get("tenure_months", 12))
    fee_pct = float(p.get("processing_fee_pct", 0.01))
    draw_in = int(p.get("draw_in_days", 7))
    moratorium = int(p.get("moratorium_months", 0))
    fee = int(amount * fee_pct)
    emi = _amortised_emi(amount, rate, tenure)
    fi.inflows.append(ScheduledInflow(
        invoice_id="scn-loan-draw", counterparty_id="scn-lender",
        amount_paise=amount - fee, day_offset=float(draw_in), sigma_days=2.0,
        label="Working-capital loan drawdown (net of fee)"))
    months = max(1, (fi.horizon_weeks * 7 - draw_in) // 30 + 1)
    _add_monthly(fi, "Working-capital loan EMI", "loan_emi", emi,
                 draw_in + 30 * (moratorium + 1), months)
    in_horizon_emis = min(months, max(0, (fi.horizon_weeks * 7 - draw_in - 30 * (moratorium + 1)) // 30 + 1))
    return {"amount_paise": amount, "processing_fee_paise": fee, "emi_paise": emi,
            "annual_rate": rate, "tenure_months": tenure,
            "total_cost_paise": emi * tenure - amount + fee,
            "in_horizon_repayment_paise": emi * in_horizon_emis,
            "narrative": (f"{format_inr(int(amount))} at {rate:.1%} for {tenure} months. "
                          f"Net Rs {(amount-fee)/100:,.0f} received after a {format_inr(int(fee))} fee; "
                          f"total cost of credit Rs {(emi*tenure-amount+fee)/100:,.0f}. "
                          f"Availability and approval are not modelled and are not implied."),
            "disclaimer": ("RUNWAY does not arrange credit and cannot predict whether any "
                           "lender will approve this facility.")}


def h_invoice_discounting(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    """Discount selected receivables - cash now, at a cost."""
    advance_pct = float(p.get("advance_pct", 0.85))
    annual_rate = float(p.get("annual_rate", 0.135))
    fee_pct = float(p.get("platform_fee_pct", 0.004))
    settle_in = int(p.get("settlement_days", 2))
    ids = set(p.get("invoice_ids") or [])
    max_amount = int(p.get("max_amount_paise", 0))

    chosen: list[ScheduledInflow] = []
    if ids:
        chosen = [i for i in fi.inflows if i.invoice_id in ids]
    else:
        # Discount the slowest-paying invoices first: that is where the
        # financing cost buys the most time.
        for i in sorted(fi.inflows, key=lambda x: -x.day_offset):
            if max_amount and sum(c.amount_paise for c in chosen) >= max_amount:
                break
            chosen.append(i)
    if not chosen:
        raise ScenarioError("no receivables selected for discounting")

    face = sum(i.amount_paise for i in chosen)
    total_advance, total_cost = 0, 0
    chosen_ids = {id(i) for i in chosen}
    for i in chosen:
        days = max(1.0, i.day_offset)
        adv = int(i.amount_paise * advance_pct)
        interest = int(adv * annual_rate * days / 365.0)
        fee = int(i.amount_paise * fee_pct)
        total_advance += adv - interest - fee
        total_cost += interest + fee
    # Replace the original schedule: cash now, then the retained margin later.
    fi.inflows = [i for i in fi.inflows if id(i) not in chosen_ids]
    fi.inflows.append(ScheduledInflow(
        invoice_id="scn-discount-advance", counterparty_id="scn-financier",
        amount_paise=total_advance, day_offset=float(settle_in), sigma_days=1.0,
        label=f"Invoice discounting advance on {len(chosen)} invoices"))
    retained = face - sum(int(i.amount_paise * advance_pct) for i in chosen)
    if retained > 0:
        fi.inflows.append(ScheduledInflow(
            invoice_id="scn-discount-retention", counterparty_id="scn-financier",
            amount_paise=retained,
            day_offset=float(max(i.day_offset for i in chosen) + 5), sigma_days=8.0,
            label="Retention released after buyer settles"))
    eff_rate = (total_cost / max(1, total_advance)) * (365 / max(1.0, sum(
        i.day_offset for i in chosen) / len(chosen)))
    return {"invoices_discounted": len(chosen), "face_value_paise": face,
            "net_advance_paise": total_advance, "financing_cost_paise": total_cost,
            "effective_annualised_rate": round(eff_rate, 4),
            "narrative": (f"{len(chosen)} invoices worth {format_inr(int(face))} discounted for "
                          f"{format_inr(int(total_advance))} now at a cost of {format_inr(int(total_cost))} "
                          f"({eff_rate:.1%} annualised)."),
            "disclaimer": ("Eligibility on TReDS or with any financier depends on buyer "
                           "acceptance and is not modelled here.")}


def h_supplier_terms(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    extra = float(_p(fi, p, "extra_days", 15))
    only_flexible = bool(p.get("respect_msmed", True))
    moved, amount = 0, 0
    for o in fi.outflows:
        if o.kind != "supplier_invoice":
            continue
        if only_flexible and not o.flexible:
            continue   # statutory MSMED deadline - not negotiable
        o.day_offset += extra
        moved += 1
        amount += o.amount_paise
    return {"invoices_rescheduled": moved, "amount_paise": amount, "extra_days": extra,
            "respected_msmed": only_flexible,
            "narrative": (f"{moved} supplier invoices worth {format_inr(int(amount))} deferred "
                          f"{extra:.0f} days."
                          + (" Invoices covered by the MSMED 45/15-day rule were left "
                             "untouched." if only_flexible else
                             " WARNING: this includes micro/small suppliers protected by "
                             "MSMED s.15 - deferring those risks a 43B(h) disallowance."))}


def h_defer_purchase(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    amount = int(_p(fi, p, "amount_paise"))
    defer_days = int(p.get("defer_days", 60))
    orig = int(p.get("original_day_offset", 30))
    fi.outflows.append(ScheduledOutflow(
        label="Planned purchase (deferred)", kind="capex", amount_paise=amount,
        day_offset=float(orig + defer_days), sigma_days=3.0, flexible=True))
    return {"amount_paise": amount, "deferred_days": defer_days,
            "narrative": f"{format_inr(int(amount))} purchase moved out {defer_days} days."}


def h_one_off_expense(fi: ForecastInputs, p: dict, as_of: date) -> dict:
    amount = int(_p(fi, p, "amount_paise"))
    in_days = int(p.get("in_days", 14))
    fi.outflows.append(ScheduledOutflow(
        label=p.get("label", "Unplanned expense"), kind="other",
        amount_paise=amount, day_offset=float(in_days), sigma_days=2.0, flexible=False))
    return {"amount_paise": amount, "in_days": in_days,
            "narrative": f"{format_inr(int(amount))} unplanned expense on day {in_days}."}


HANDLERS: dict[str, Callable] = {
    ScenarioKind.NEW_ORDER: h_new_order,
    ScenarioKind.PAYMENT_DELAY: h_payment_delay,
    ScenarioKind.CUSTOMER_DEFAULT: h_customer_default,
    ScenarioKind.REVENUE_SHOCK: h_revenue_shock,
    ScenarioKind.COST_INCREASE: h_cost_increase,
    ScenarioKind.HIRING: h_hiring,
    ScenarioKind.EQUIPMENT_PURCHASE: h_equipment,
    ScenarioKind.FINANCING: h_financing,
    ScenarioKind.INVOICE_DISCOUNTING: h_invoice_discounting,
    ScenarioKind.SUPPLIER_TERMS: h_supplier_terms,
    ScenarioKind.DEFER_PURCHASE: h_defer_purchase,
    ScenarioKind.ONE_OFF_EXPENSE: h_one_off_expense,
}


def apply_scenario(baseline: ForecastInputs, kind: str, params: dict,
                   as_of: date) -> tuple[ForecastInputs, dict]:
    """Return a **new** ForecastInputs plus the scenario's own economics.

    ``baseline`` is never mutated: isolation is enforced by copying here, in
    one place, rather than trusting every handler.
    """
    fi = baseline.copy()
    extras: dict = {}
    if kind == ScenarioKind.COMPOSITE:
        steps = params.get("steps") or []
        if not steps:
            raise ScenarioError("a composite scenario needs at least one step")
        extras["steps"] = []
        for s in steps:
            k = s.get("kind")
            if k not in HANDLERS:
                raise ScenarioError(f"unknown scenario step '{k}'")
            extras["steps"].append({"kind": k, **HANDLERS[k](fi, s.get("params", {}), as_of)})
        extras["narrative"] = " ".join(s.get("narrative", "") for s in extras["steps"])
    else:
        if kind not in HANDLERS:
            raise ScenarioError(f"unknown scenario kind '{kind}'")
        extras = HANDLERS[kind](fi, params, as_of)
    fi.assumptions = {**fi.assumptions, "scenario_kind": kind,
                      "scenario_params": params, "scenario_economics": extras}
    return fi, extras


# ───────────────────── catalogue for the UI ──────────────────────────

CATALOGUE: list[dict] = [
    {"kind": ScenarioKind.NEW_ORDER, "label": "Accept a new order",
     "question": "Can I afford to take this order?",
     "description": "Models advance, material purchase, production time and the credit period.",
     "params": [
         {"key": "order_value_paise", "label": "Order value", "kind": "money", "default": 15_00_000_00},
         {"key": "margin_pct", "label": "Gross margin", "kind": "percent", "default": 0.18, "min": 0, "max": 0.9},
         {"key": "advance_pct", "label": "Advance received", "kind": "percent", "default": 0.0, "min": 0, "max": 1},
         {"key": "credit_days", "label": "Customer credit period", "kind": "days", "default": 60},
         {"key": "production_days", "label": "Production / fulfilment time", "kind": "days", "default": 21},
         {"key": "supplier_credit_days", "label": "Supplier credit period", "kind": "days", "default": 30},
         {"key": "start_in_days", "label": "Starts in", "kind": "days", "default": 7}]},
    {"kind": ScenarioKind.PAYMENT_DELAY, "label": "A customer pays late",
     "question": "What if my biggest customer pays 30 days late?",
     "description": "Shifts that customer's open invoices later.",
     "params": [
         {"key": "counterparty_id", "label": "Customer", "kind": "select", "default": "largest"},
         {"key": "delay_days", "label": "Extra delay", "kind": "days", "default": 30}]},
    {"kind": ScenarioKind.CUSTOMER_DEFAULT, "label": "A customer defaults",
     "question": "What if my largest customer stops paying altogether?",
     "description": "Removes that customer's open exposure, net of any assumed recovery.",
     "params": [
         {"key": "counterparty_id", "label": "Customer", "kind": "select", "default": "largest"},
         {"key": "recovery_pct", "label": "Assumed recovery", "kind": "percent", "default": 0.0}]},
    {"kind": ScenarioKind.REVENUE_SHOCK, "label": "Revenue falls",
     "question": "What happens if revenue drops 20%?",
     "description": "Reduces sales not yet invoiced. Already-issued invoices are unaffected.",
     "params": [{"key": "drop_pct", "label": "Revenue drop", "kind": "percent", "default": 0.20}]},
    {"kind": ScenarioKind.COST_INCREASE, "label": "Input costs rise",
     "question": "What if my raw material prices go up?",
     "description": "Raises the cost ratio on forecast purchases and, optionally, open bills.",
     "params": [
         {"key": "increase_pct", "label": "Cost increase", "kind": "percent", "default": 0.10},
         {"key": "scope", "label": "Applies to", "kind": "select", "default": "materials",
          "options": [{"value": "materials", "label": "Future purchases"},
                      {"value": "open_bills", "label": "Open bills"},
                      {"value": "both", "label": "Both"}]}]},
    {"kind": ScenarioKind.HIRING, "label": "Hire people",
     "question": "Can I afford two more people?",
     "description": "Adds payroll now and a risk-adjusted, ramped revenue benefit later.",
     "params": [
         {"key": "headcount", "label": "People", "kind": "int", "default": 2},
         {"key": "monthly_cost_per_head_paise", "label": "Cost per person per month", "kind": "money", "default": 35_000_00},
         {"key": "start_in_days", "label": "Joining in", "kind": "days", "default": 30},
         {"key": "expected_monthly_revenue_uplift_paise", "label": "Hoped-for monthly revenue uplift", "kind": "money", "default": 0},
         {"key": "uplift_probability", "label": "Probability the uplift happens", "kind": "percent", "default": 0.5},
         {"key": "uplift_ramp_months", "label": "Months before any uplift", "kind": "int", "default": 3}]},
    {"kind": ScenarioKind.EQUIPMENT_PURCHASE, "label": "Buy equipment",
     "question": "Should I buy this machine now?",
     "description": "Down payment, EMI, maintenance and the operational saving it claims.",
     "params": [
         {"key": "cost_paise", "label": "Equipment cost", "kind": "money", "default": 9_50_000_00},
         {"key": "down_payment_pct", "label": "Down payment", "kind": "percent", "default": 0.25},
         {"key": "annual_rate", "label": "Loan rate", "kind": "percent", "default": 0.135},
         {"key": "tenure_months", "label": "Tenure", "kind": "int", "default": 36},
         {"key": "monthly_saving_paise", "label": "Expected monthly saving", "kind": "money", "default": 20_000_00},
         {"key": "monthly_maintenance_paise", "label": "Monthly maintenance", "kind": "money", "default": 4_000_00}]},
    {"kind": ScenarioKind.FINANCING, "label": "Take working capital",
     "question": "What does borrowing actually cost me?",
     "description": "Drawdown net of fees, then EMIs. Approval is never assumed.",
     "params": [
         {"key": "amount_paise", "label": "Facility amount", "kind": "money", "default": 10_00_000_00},
         {"key": "annual_rate", "label": "Interest rate", "kind": "percent", "default": 0.16},
         {"key": "tenure_months", "label": "Tenure", "kind": "int", "default": 12},
         {"key": "processing_fee_pct", "label": "Processing fee", "kind": "percent", "default": 0.01},
         {"key": "moratorium_months", "label": "Moratorium", "kind": "int", "default": 0}]},
    {"kind": ScenarioKind.INVOICE_DISCOUNTING, "label": "Discount receivables",
     "question": "Should I discount invoices instead of borrowing?",
     "description": "Sells the slowest receivables for cash now at a stated cost.",
     "params": [
         {"key": "max_amount_paise", "label": "Up to", "kind": "money", "default": 10_00_000_00},
         {"key": "advance_pct", "label": "Advance rate", "kind": "percent", "default": 0.85},
         {"key": "annual_rate", "label": "Discount rate", "kind": "percent", "default": 0.135},
         {"key": "platform_fee_pct", "label": "Platform fee", "kind": "percent", "default": 0.004}]},
    {"kind": ScenarioKind.SUPPLIER_TERMS, "label": "Renegotiate supplier terms",
     "question": "What if my suppliers give me more time?",
     "description": "Defers supplier payments, leaving MSMED-protected invoices alone.",
     "params": [
         {"key": "extra_days", "label": "Extra days", "kind": "days", "default": 15},
         {"key": "respect_msmed", "label": "Protect micro/small suppliers", "kind": "bool", "default": True}]},
    {"kind": ScenarioKind.DEFER_PURCHASE, "label": "Defer a planned purchase",
     "question": "How much does waiting help?",
     "description": "Moves a discretionary outflow later.",
     "params": [
         {"key": "amount_paise", "label": "Purchase amount", "kind": "money", "default": 3_00_000_00},
         {"key": "original_day_offset", "label": "Originally due in", "kind": "days", "default": 30},
         {"key": "defer_days", "label": "Defer by", "kind": "days", "default": 60}]},
    {"kind": ScenarioKind.ONE_OFF_EXPENSE, "label": "An unexpected expense",
     "question": "Can I absorb a sudden bill?",
     "description": "Adds a single unplanned outflow.",
     "params": [
         {"key": "amount_paise", "label": "Amount", "kind": "money", "default": 2_00_000_00},
         {"key": "in_days", "label": "In", "kind": "days", "default": 14},
         {"key": "label", "label": "Description", "kind": "text", "default": "Unplanned expense"}]},
]
