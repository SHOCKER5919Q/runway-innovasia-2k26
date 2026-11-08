"""Deterministic intent routing.

Which tool answers the question is decided here, by scored pattern matching,
*before* any language model is involved. Three reasons:

1. It works with no API key, so the product is demonstrable offline.
2. It is auditable - the chosen tool and the matched phrase are returned.
3. It removes an injection surface: an attacker who controls text inside a
   transaction narration cannot steer tool selection, because selection
   never sees that text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.enums import ScenarioKind


@dataclass
class Intent:
    tool: str
    args: dict = field(default_factory=dict)
    score: float = 0.0
    matched: str = ""
    followups: list[str] = field(default_factory=list)


# (tool, weight, regex)
PATTERNS: list[tuple[str, float, str]] = [
    ("get_cash_runway", 3.0, r"\brunway|how long (can|will).{0,20}(last|survive)|months? of cash|weeks? of cash"),
    ("get_actual_state", 3.0, r"\bhow much (cash|money)|current (cash|balance)|cash (in hand|position)|available (cash|liquidity)|bank balance|what.{0,6}s my cash"),
    ("get_predicted_state", 3.0, r"\bforecast|projection|next 13 weeks|13[- ]week|cash (in|by) (december|january|february|next month)|worst[- ]case|\bp10\b|\bp50\b|\bp90\b"),
    ("get_forecast_drivers", 3.1, r"what.{0,4}s driving|\bdrivers?\b|why (is|has) (the )?forecast|what moves the"),
    ("get_receivables", 3.4, r"\breceivab|who owes|outstanding (from|invoice)|\bcollect|follow up on|ageing|aging|\bdebtor"),
    ("get_customer_risk", 3.3, r"which customers?.{0,30}(delay|late|slow|risk)|customers?.{0,12}(delaying|paying late|late payment)|customer (risk|behaviour|behavior)|payment (behaviour|behavior)|\breliability"),
    ("get_payment_prediction", 3.6, r"when (will|do|does|should).{0,40}(pay|paid)|predicted payment|payment date|INV[-\s]?\d+"),
    ("get_payables", 3.0, r"\bpayab|\bsupplier|\bvendor|whom do i owe|\bcreditor|purchase bill"),
    ("get_upcoming_liabilities", 3.2, r"\bgst\b|\btds\b|statutory|\btax\b|payroll|\bsalar|obligation|due (this|next) (week|month)|how much.{0,20}reserve"),
    ("get_financial_health", 3.3, r"health score|financial health|how healthy|score (fall|fell|drop|go|chang)"),
    ("get_risk_alerts", 3.0, r"\balert|\brisks?\b|\bwarning|what should i worry|anything wrong|\bproblem"),
    ("get_recommendations", 3.2, r"\brecommend|what should i do|\badvice\b|\bsuggest|what actions?|\bpriorit"),
    ("get_stress_tests", 3.3, r"stress test|worst case|what if everything|\bsurvive\b|resilien"),
    ("get_concentration_risk", 3.0, r"concentrat|dependen|too reliant|biggest customer share|\bhhi\b"),
    ("get_transactions_summary", 2.6, r"\btransaction|\bspending\b|where (is|did) (my )?money|expenses? breakdown|\binflow|\boutflow"),
    ("evaluate_forecast_accuracy", 3.8, r"\baccura|how (good|right|close) (was|were)|track record|forecast error|\bbacktest"),
    ("get_data_quality", 3.1, r"data quality|how complete|\bstale\b|is the data|trust the (data|number)"),
    ("get_scenario_catalogue", 2.9, r"what scenarios|what can i simulate|scenario (type|option)"),
]

SCENARIO_PATTERNS: list[tuple[str, float, str]] = [
    (ScenarioKind.NEW_ORDER, 4.6, r"(accept|take on|can i afford|should i take).{0,30}\border\b|\bnew order\b|\border (of|worth|for)\b|negotiat\w*.{0,20}advance"),
    (ScenarioKind.PAYMENT_DELAY, 4.0, r"(pays?|paid).{0,20}\d{1,3}\s*days? (late|later)|delays? payment|pays? late"),
    (ScenarioKind.CUSTOMER_DEFAULT, 4.2, r"\bdefaults?\b|stops paying|never pays|goes (bust|under)|insolven"),
    (ScenarioKind.REVENUE_SHOCK, 4.0, r"revenue (drops?|falls?|declines?|down)|sales (drop|fall)"),
    (ScenarioKind.COST_INCREASE, 4.0, r"(cost|price|material).{0,20}(rise|rises|increase|goes? up|up by)"),
    (ScenarioKind.HIRING, 4.0, r"\bhire|hiring|recruit|new (employee|staff|people)|(more|another|two|three|four|\d+) (new )?(employee|staff|people|hire)"),
    (ScenarioKind.EQUIPMENT_PURCHASE, 4.4, r"(buy|purchase|buying).{0,25}(machine|equipment|vehicle|plant|sealer)|\bcapex\b"),
    (ScenarioKind.FINANCING, 4.0, r"\bloan\b|\bborrow|working capital (facility|finance|loan)|od limit|credit line"),
    (ScenarioKind.INVOICE_DISCOUNTING, 4.3, r"invoice discount|bill discount|\btreds\b|factoring"),
    (ScenarioKind.SUPPLIER_TERMS, 4.1, r"supplier (terms|credit)|more time to pay|extend.{0,15}terms|negotiate.{0,15}supplier"),
    (ScenarioKind.DEFER_PURCHASE, 3.6, r"(defer|postpone).{0,20}(purchase|buying|spend)"),
    (ScenarioKind.ONE_OFF_EXPENSE, 3.4, r"(unexpected|sudden|unplanned).{0,15}(expense|bill|cost)"),
    # "Can I afford Rs X?" is an affordability test: a one-off outflow of X
    # simulated against the forecast. It is the single most common question
    # an MSME owner actually asks, so it gets the highest weight.
    (ScenarioKind.ONE_OFF_EXPENSE, 4.8, r"can i afford.{0,40}(\d|\brs\b|₹|lakh|crore|purchase|buy|spend)"),
]

_AMOUNT = re.compile(
    r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(cr(?:ore)?s?|lakhs?|lacs?|l\b|k\b|thousand)?",
    re.I)
_DAYS = re.compile(r"(\d{1,3})\s*days?", re.I)
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|per ?cent)", re.I)
_COUNT = re.compile(r"\b(\d{1,3})\s*(?:new\s+)?(?:people|employees?|staff|hires?|workers?)\b", re.I)
_INVOICE = re.compile(r"\b(INV[-\s]?\d+|PUR[-\s]?\d+)\b", re.I)


def parse_amount_paise(text: str) -> int | None:
    best = None
    for m in _AMOUNT.finditer(text):
        raw, unit = m.group(1), (m.group(2) or "").lower()
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        if unit.startswith("cr"):
            v *= 1_00_00_000
        elif unit.startswith(("lakh", "lac", "l")):
            v *= 1_00_000
        elif unit.startswith(("k", "thousand")):
            v *= 1_000
        elif v < 1000:
            continue          # "30 days" / "2 people" are not money
        p = int(round(v * 100))
        if best is None or p > best:
            best = p
    return best


def route(question: str, *, known_customers: list[str] | None = None) -> Intent:
    q = (question or "").strip()
    ql = q.lower()
    if not ql:
        return Intent("get_recommendations", score=0.1, matched="empty question")

    # Scenario questions win when present - they are the product's point.
    best_scn, best_scn_score, best_scn_match = None, 0.0, ""
    for kind, w, pat in SCENARIO_PATTERNS:
        m = re.search(pat, ql)
        if m and w > best_scn_score:
            best_scn, best_scn_score, best_scn_match = kind, w, m.group(0)
    conditional = bool(re.search(r"\b(what if|if i|should i|can i afford|suppose|imagine|what happens if)\b", ql))
    if best_scn and (conditional or best_scn_score >= 4.0):
        return Intent("run_scenario",
                      {"kind": best_scn, "params": _scenario_params(best_scn, q, ql,
                                                                    known_customers)},
                      score=best_scn_score + (1.0 if conditional else 0.0),
                      matched=best_scn_match,
                      followups=_followups_for(best_scn))

    best, score, matched = "get_recommendations", 0.0, ""
    for tool, w, pat in PATTERNS:
        m = re.search(pat, ql)
        if m and w > score:
            best, score, matched = tool, w, m.group(0)

    args: dict = {}
    if best == "get_customer_risk" and known_customers:
        for name in known_customers:
            if name.lower().split()[0] in ql:
                args["customer"] = name
                break
    if best == "get_payment_prediction":
        im = _INVOICE.search(q)
        if im:
            args["invoice_no"] = im.group(1).upper().replace(" ", "-")
        elif known_customers:
            for name in known_customers:
                if name.lower().split()[0] in ql:
                    args["customer"] = name
                    break
    return Intent(best, args, score=score, matched=matched)


def _scenario_params(kind: str, q: str, ql: str, customers: list[str] | None) -> dict:
    amt = parse_amount_paise(q)
    days = int(_DAYS.search(ql).group(1)) if _DAYS.search(ql) else None
    pct = float(_PCT.search(ql).group(1)) / 100 if _PCT.search(ql) else None
    count = int(_COUNT.search(ql).group(1)) if _COUNT.search(ql) else None
    cp = None
    if customers:
        for name in customers:
            if name.lower().split()[0] in ql:
                cp = name
                break

    if kind == ScenarioKind.NEW_ORDER:
        p = {"order_value_paise": amt or 15_00_000_00,
             "margin_pct": pct if (pct and pct < 0.6) else 0.18,
             "advance_pct": 0.0, "credit_days": days or 60,
             "production_days": 21, "supplier_credit_days": 30, "start_in_days": 7}
        adv = re.search(r"(\d{1,3})\s*%\s*advance", ql)
        if adv:
            p["advance_pct"] = float(adv.group(1)) / 100
        return p
    if kind == ScenarioKind.PAYMENT_DELAY:
        return {"counterparty_id": cp or "largest", "delay_days": days or 30}
    if kind == ScenarioKind.CUSTOMER_DEFAULT:
        return {"counterparty_id": cp or "largest", "recovery_pct": 0.0}
    if kind == ScenarioKind.REVENUE_SHOCK:
        return {"drop_pct": pct or 0.20}
    if kind == ScenarioKind.COST_INCREASE:
        return {"increase_pct": pct or 0.10, "scope": "materials"}
    if kind == ScenarioKind.HIRING:
        return {"headcount": count or 2,
                "monthly_cost_per_head_paise": amt if (amt and amt < 5_00_000_00) else 35_000_00,
                "start_in_days": 30, "expected_monthly_revenue_uplift_paise": 0,
                "uplift_probability": 0.5, "uplift_ramp_months": 3}
    if kind == ScenarioKind.EQUIPMENT_PURCHASE:
        return {"cost_paise": amt or 9_50_000_00, "down_payment_pct": 0.25,
                "annual_rate": 0.135, "tenure_months": 36,
                "monthly_saving_paise": 20_000_00, "monthly_maintenance_paise": 4_000_00}
    if kind == ScenarioKind.FINANCING:
        return {"amount_paise": amt or 10_00_000_00, "annual_rate": pct or 0.16,
                "tenure_months": 12, "processing_fee_pct": 0.01}
    if kind == ScenarioKind.INVOICE_DISCOUNTING:
        return {"max_amount_paise": amt or 10_00_000_00, "advance_pct": 0.85,
                "annual_rate": 0.135, "platform_fee_pct": 0.004}
    if kind == ScenarioKind.SUPPLIER_TERMS:
        return {"extra_days": days or 15, "respect_msmed": True}
    if kind == ScenarioKind.DEFER_PURCHASE:
        return {"amount_paise": amt or 3_00_000_00, "original_day_offset": 30,
                "defer_days": days or 60}
    if kind == ScenarioKind.ONE_OFF_EXPENSE:
        return {"amount_paise": amt or 2_00_000_00, "in_days": days or 14,
                "label": "Unplanned expense"}
    return {}


def _followups_for(kind: str) -> list[str]:
    base = {
        ScenarioKind.NEW_ORDER: ["What if I negotiate a 30% advance?",
                                 "Compare accepting with and without invoice discounting",
                                 "What if the customer then pays 30 days late?"],
        ScenarioKind.PAYMENT_DELAY: ["Which other customers are at risk of doing the same?",
                                     "What would discounting those invoices cost?"],
        ScenarioKind.FINANCING: ["Compare this against invoice discounting",
                                 "What happens if I collect overdue invoices instead?"],
        ScenarioKind.HIRING: ["What if the revenue uplift does not arrive?",
                              "Can I afford this three months later instead?"],
    }
    return base.get(kind, ["Compare this against the baseline forecast",
                           "What would make this safer?"])
