"""The deterministic recommendation engine.

Rules, not a language model. Each rule inspects the state bundle and, if it
fires, emits a fully-evidenced recommendation. Ranking is an explicit linear
score whose terms are published alongside the result, so an owner can see
why one action sits above another and disagree with the weighting.

Hard constraints, enforced in code rather than in prose:

* RUNWAY never executes a payment, applies for credit or alters a contract.
  Every recommendation carries ``requires_approval``.
* Borrowing is never recommended on its own merits. It is only offered after
  the cost of the facility has been compared against the cost of the
  shortfall it would cover, and the comparison is shown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.enums import ScenarioKind
from app.core.money import format_inr


@dataclass
class Rec:
    code: str
    title: str
    priority: int
    score_terms: dict
    trigger_evidence: list[dict]
    expected_effect_paise: int
    expected_effect_text: str
    downside_text: str
    required_action: str
    deadline: date | None
    confidence: float
    explanation: str
    linked_scenario: dict | None = None
    requires_approval: bool = True
    tags: list[str] = field(default_factory=list)


def _score(*, urgency: float, impact: float, confidence: float,
           effort: float, reversibility: float) -> tuple[int, dict]:
    """Explainable ranking.

    urgency        0-1  how soon it stops mattering
    impact         0-1  size of the cash effect relative to the buffer
    confidence     0-1  how well-evidenced the trigger is
    effort         0-1  1 = trivial for the owner to do
    reversibility  0-1  1 = fully reversible if it turns out wrong
    """
    terms = {"urgency": round(urgency, 3), "impact": round(impact, 3),
             "confidence": round(confidence, 3), "ease": round(effort, 3),
             "reversibility": round(reversibility, 3)}
    weights = {"urgency": 0.30, "impact": 0.30, "confidence": 0.20,
               "ease": 0.12, "reversibility": 0.08}
    total = sum(terms[k] * w for k, w in weights.items())
    terms["weights"] = weights
    terms["formula"] = " + ".join(f"{w}*{k}" for k, w in weights.items())
    return int(round(100 * total)), terms


def generate(*, business, as_of: date, position, simulation, behaviour, collection_list,
             ageing_ar, concentration, coverage, msmed, supplier_profiles, health,
             anomalies, stress_results, obligations) -> list[Rec]:
    buffer = max(1, business.safety_buffer_paise)
    recs: list[Rec] = []
    shortfall = max(0, buffer - simulation.min_cash_p10_paise) if simulation else 0

    # ── 1. chase the invoices that matter ──────────────────────────
    top = [c for c in collection_list if c["days_past_due"] > 0][:5]
    if top:
        amount = sum(c["outstanding_paise"] for c in top)
        pr, terms = _score(urgency=min(1.0, max(c["days_past_due"] for c in top) / 45),
                           impact=min(1.0, amount / buffer), confidence=0.9,
                           effort=0.9, reversibility=1.0)
        recs.append(Rec(
            code="collect_overdue", title=f"Collect {format_inr(amount)} from {len(top)} overdue invoices",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": f"{c['customer']} {c['invoice_no']}",
                               "value": f"{format_inr(c['outstanding_paise'])}, "
                                        f"{c['days_past_due']} days past due"} for c in top],
            expected_effect_paise=amount,
            expected_effect_text=(f"Collecting these would lift minimum cash by up to "
                                  f"{format_inr(amount)} and is the cheapest liquidity "
                                  f"available - it costs a phone call, not interest."),
            downside_text=("Pressing a strategic buyer too hard can cost future orders. "
                           "Start with a statement, escalate only if ignored."),
            required_action="Work the prioritised collection list from the top.",
            deadline=as_of + timedelta(days=7), confidence=0.9,
            explanation=("Ranked by outstanding amount, days past due and the customer's "
                         "measured reliability. Nothing here is estimated - every figure "
                         "comes from an issued invoice."),
            tags=["receivables", "free_liquidity"]))

    # ── 2. ring-fence statutory money ──────────────────────────────
    stat = [o for o in obligations["items"] if o["statutory"] and not o["overdue"]
            and o["days_away"] <= 30]
    if stat:
        amt = sum(o["amount_paise"] for o in stat)
        soonest = min(o["days_away"] for o in stat)
        pr, terms = _score(urgency=min(1.0, (31 - soonest) / 31),
                           impact=min(1.0, amt / buffer), confidence=0.75,
                           effort=0.95, reversibility=1.0)
        recs.append(Rec(
            code="reserve_statutory", title=f"Reserve {format_inr(amt)} for statutory dues",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": o["label"],
                               "value": f"{format_inr(o['amount_paise'])} due in {o['days_away']} days"
                                        + (" (RUNWAY estimate, not a filed figure)"
                                           if o["is_estimated"] else "")} for o in stat],
            expected_effect_paise=amt,
            expected_effect_text=("Avoids 18% a year interest plus late fee on GST, and keeps "
                                  "the compliance record clean."),
            downside_text="Reserved cash is unavailable for operations until the due date.",
            required_action="Mark these obligations as cash-reserved in the Compliance Calendar.",
            deadline=as_of + timedelta(days=max(1, soonest - 2)), confidence=0.75,
            explanation=("GST liability is RUNWAY's estimate from output tax on recorded sales "
                         "less input credit on recorded purchases. Confirm it on the GST portal "
                         "before paying."),
            tags=["compliance", "gst"]))

    # ── 3. MSMED / 43B(h) ──────────────────────────────────────────
    if msmed["already_breached_paise"] > 0 or msmed["due_within_14_days_paise"] > 0:
        amt = msmed["already_breached_paise"] + msmed["due_within_14_days_paise"]
        pr, terms = _score(urgency=1.0 if msmed["already_breached_paise"] else 0.7,
                           impact=min(1.0, amt / buffer), confidence=0.7,
                           effort=0.8, reversibility=0.6)
        recs.append(Rec(
            code="pay_msme_suppliers",
            title=f"Clear {format_inr(amt)} owed to micro/small suppliers",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": i["invoice_no"],
                               "value": f"{i['supplier']} ({i['msme_class']}) "
                                        f"{format_inr(i['amount_paise'])}, deadline "
                                        f"{i['statutory_deadline']}"}
                              for i in msmed["items"][:6]],
            expected_effect_paise=-amt,
            expected_effect_text=("Protects the deduction for these purchases under "
                                  "Income-tax s.43B(h)."),
            downside_text="Paying early consumes cash in a week where it may be tight.",
            required_action="Prioritise these in the next payment run.",
            deadline=as_of + timedelta(days=7), confidence=0.7,
            explanation=msmed["rule"] + " " + msmed["caveat"],
            tags=["compliance", "payables", "msmed"]))

    # ── 4. early-payment discounts worth taking ────────────────────
    for s in supplier_profiles:
        if s.discount_opportunity_paise <= 0 or not s.discount_annualised_return:
            continue
        if s.discount_annualised_return <= business.max_borrowing_apr:
            continue
        pr, terms = _score(urgency=0.5,
                           impact=min(1.0, s.discount_opportunity_paise / buffer),
                           confidence=0.85, effort=0.85, reversibility=0.4)
        recs.append(Rec(
            code="take_early_discount",
            title=f"Take {s.name}'s early-payment discount ({format_inr(s.discount_opportunity_paise)})",
            priority=pr, score_terms=terms,
            trigger_evidence=[
                {"label": "Discount offered", "value": f"{s.early_discount_pct:.2%} within {s.early_discount_days} days"},
                {"label": "Annualised equivalent", "value": f"{s.discount_annualised_return:.1%}"},
                {"label": "Your borrowing-cost ceiling", "value": f"{business.max_borrowing_apr:.0%}"},
                {"label": "Eligible invoices", "value": f"{s.invoices_open} open"}],
            expected_effect_paise=s.discount_opportunity_paise,
            expected_effect_text=(f"Equivalent to a {s.discount_annualised_return:.1%} annualised "
                                  f"return on the cash used, against a "
                                  f"{business.max_borrowing_apr:.0%} cost of credit."),
            downside_text=("Only worth it if the forecast shows the cash is genuinely spare "
                           "in that week. Run it in the Scenario Lab first."),
            required_action="Confirm the discount with the supplier in writing, then pay early.",
            deadline=as_of + timedelta(days=max(1, s.early_discount_days)), confidence=0.85,
            explanation=("Annualised cost of forgoing a discount d over n days saved is "
                         "(d / (1 - d)) x (365 / n)."),
            tags=["payables", "yield"]))

    # ── 5. liquidity gap: compare the real options ─────────────────
    if shortfall > 0 and simulation:
        collectable = sum(c["outstanding_paise"] for c in collection_list
                          if c["days_past_due"] > 0)
        options = [
            {"option": "Collect overdue receivables",
             "liquidity_paise": collectable, "cost_paise": 0,
             "cost_note": "No financing cost. Needs collection effort and goodwill.",
             "speed_days": 10, "certainty": "medium"},
            {"option": "Defer discretionary purchases",
             "liquidity_paise": sum(o["amount_paise"] for o in obligations["items"]
                                    if o["kind"] in ("other", "insurance")),
             "cost_paise": 0, "cost_note": "No cost where no contract is breached.",
             "speed_days": 1, "certainty": "high"},
            {"option": "Draw sanctioned overdraft",
             "liquidity_paise": position.overdraft_headroom_paise,
             "cost_paise": int(position.overdraft_headroom_paise * 0.14 * 60 / 365),
             "cost_note": "Interest on the drawn amount for roughly 60 days at ~14%.",
             "speed_days": 1, "certainty": "high"},
            {"option": "Discount receivables",
             "liquidity_paise": int(sum(c["outstanding_paise"] for c in collection_list) * 0.85),
             "cost_paise": int(sum(c["outstanding_paise"] for c in collection_list) * 0.85
                               * 0.135 * 45 / 365),
             "cost_note": "Discount charge for ~45 days at ~13.5% plus platform fee. "
                          "Buyer acceptance required; eligibility is not guaranteed.",
             "speed_days": 3, "certainty": "medium"},
            {"option": "New working-capital loan",
             "liquidity_paise": shortfall,
             "cost_paise": int(shortfall * 0.16 * 365 / 365) + int(shortfall * 0.01),
             "cost_note": "A year of interest at ~16% plus a 1% processing fee. "
                          "Approval is not implied and RUNWAY does not arrange credit.",
             "speed_days": 21, "certainty": "low"},
        ]
        for o in options:
            o["covers_gap"] = o["liquidity_paise"] >= shortfall
            o["cost_per_rupee"] = (round(o["cost_paise"] / o["liquidity_paise"], 4)
                                   if o["liquidity_paise"] > 0 else None)
        viable = [o for o in options if o["liquidity_paise"] > 0]
        viable.sort(key=lambda o: (not o["covers_gap"], o["cost_paise"], o["speed_days"]))
        pr, terms = _score(urgency=min(1.0, simulation.breach_probability * 2),
                           impact=min(1.0, shortfall / buffer), confidence=0.7,
                           effort=0.5, reversibility=0.7)
        recs.append(Rec(
            code="close_liquidity_gap",
            title=f"Close a potential {format_inr(shortfall)} liquidity gap",
            priority=pr, score_terms=terms,
            trigger_evidence=[
                {"label": "Breach probability", "value": f"{simulation.breach_probability:.0%}"},
                {"label": "Minimum cash P10", "value": format_inr(simulation.min_cash_p10_paise)},
                {"label": "Safety buffer", "value": format_inr(buffer)},
                {"label": "Liquidity CVaR (95%)", "value": format_inr(simulation.liquidity_cvar_paise)}],
            expected_effect_paise=shortfall,
            expected_effect_text=(f"The cheapest option that covers the gap is "
                                  f"'{viable[0]['option']}' at a cost of "
                                  f"{format_inr(viable[0]['cost_paise'])}."
                                  if viable else "No single option covers the gap."),
            downside_text=("Borrowing converts a timing problem into a fixed obligation. "
                           "Take it only after the free options are exhausted."),
            required_action="Review the funding comparison and choose; RUNWAY will not act for you.",
            deadline=(date.fromisoformat(simulation.week_starts[simulation.first_breach_week_p50])
                      - timedelta(days=10)) if simulation.first_breach_week_p50 else None,
            confidence=0.7,
            explanation=("Options are ranked by whether they cover the gap, then by cost, "
                         "then by speed. Costs are indicative at the stated rates; actual "
                         "pricing depends on the lender."),
            linked_scenario={"kind": ScenarioKind.FINANCING,
                             "params": {"amount_paise": shortfall, "annual_rate": 0.16,
                                        "tenure_months": 12}},
            tags=["liquidity", "financing"], requires_approval=True))
        recs[-1].score_terms["funding_options"] = viable

    # ── 6. concentration ───────────────────────────────────────────
    if concentration["top1_share"] > business.max_customer_concentration:
        top1 = concentration["top_counterparties"][0]
        pr, terms = _score(urgency=0.35, impact=min(1.0, top1["outstanding_paise"] / buffer),
                           confidence=0.95, effort=0.25, reversibility=0.9)
        recs.append(Rec(
            code="reduce_concentration",
            title=f"Set a credit limit for {top1['name']} and develop alternatives",
            priority=pr, score_terms=terms,
            trigger_evidence=[
                {"label": "Revenue share", "value": f"{top1['share']:.0%} (policy {business.max_customer_concentration:.0%})"},
                {"label": "Open exposure", "value": format_inr(top1["outstanding_paise"])},
                {"label": "HHI", "value": f"{concentration['counterparty_hhi']:.3f}"}],
            expected_effect_paise=0,
            expected_effect_text="Structural risk reduction rather than an immediate cash effect.",
            downside_text="Capping supply to your biggest buyer costs short-term revenue.",
            required_action="Agree an internal exposure cap and open two mid-sized accounts.",
            deadline=None, confidence=0.95,
            explanation=("Measured as Herfindahl-Hirschman concentration over 12 months of "
                         "billing, the same index used for portfolio single-name risk."),
            linked_scenario={"kind": ScenarioKind.CUSTOMER_DEFAULT,
                             "params": {"counterparty_id": top1["counterparty_id"],
                                        "recovery_pct": 0.3}},
            tags=["risk", "concentration"]))

    # ── 7. unreviewed anomalies ────────────────────────────────────
    dups = [a for a in anomalies if a["kind"] == "possible_duplicate_payment"]
    if dups:
        amt = sum(a["amount_paise"] for a in dups)
        pr, terms = _score(urgency=0.8, impact=min(1.0, amt / buffer), confidence=0.6,
                           effort=0.95, reversibility=1.0)
        recs.append(Rec(
            code="review_duplicates", title=f"Review {len(dups)} possible duplicate payments",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": a["date"], "value": a["why"]} for a in dups[:5]],
            expected_effect_paise=amt,
            expected_effect_text=f"Up to {format_inr(amt)} may be recoverable from suppliers.",
            downside_text="Some will be genuine repeat payments; confirm before claiming.",
            required_action="Open each transaction and confirm against the supplier's statement.",
            deadline=as_of + timedelta(days=14), confidence=0.6,
            explanation=("Flagged where two debits of the same amount reached the same "
                         "counterparty within 7 days with no distinguishing bank reference."),
            tags=["controls", "recovery"]))

    # ── 8. stress-test failures ────────────────────────────────────
    fatal = [s for s in stress_results if not s["survives_with_overdraft"]]
    if fatal:
        worst = fatal[0]
        pr, terms = _score(urgency=0.45, impact=1.0, confidence=0.6, effort=0.3,
                           reversibility=0.8)
        recs.append(Rec(
            code="stress_failure",
            title=f"The business does not survive '{worst['label']}' even with the overdraft",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": s["label"],
                               "value": f"min cash P10 {format_inr(s['min_cash_p10_paise'])}, "
                                        f"runway {s['runway_weeks_p50']}w"} for s in fatal[:4]],
            expected_effect_paise=abs(worst["min_cash_p10_paise"]),
            expected_effect_text=("Building the buffer or a standby facility turns these "
                                  "from fatal into survivable."),
            downside_text="Holding more idle cash lowers the return on capital employed.",
            required_action=("Raise the safety buffer, or arrange a standby facility sized "
                             "to the worst surviving gap."),
            deadline=None, confidence=0.6,
            explanation=("Each stress test re-simulates with the same random draws as the "
                         "baseline, so the difference is the shock and not noise."),
            tags=["resilience", "stress"]))

    # ── 9. the weakest health dimension ────────────────────────────
    weakest = min(health["subscores"], key=lambda s: s["score"])
    if weakest["score"] < 50:
        pr, terms = _score(urgency=0.25, impact=0.4, confidence=0.8, effort=0.4,
                           reversibility=1.0)
        recs.append(Rec(
            code=f"improve_{weakest['key']}",
            title=f"Improve {weakest['label'].lower()} - your weakest dimension",
            priority=pr, score_terms=terms,
            trigger_evidence=[{"label": "Score", "value": f"{weakest['score']}/100 ({weakest['band']})"}]
                             + [{"label": "Driver", "value": e} for e in weakest["evidence"]],
            expected_effect_paise=0,
            expected_effect_text=(f"Moving this to 70 would lift the overall score by about "
                                 f"{(70 - weakest['score']) * weakest['weight']:.1f} points."),
            downside_text="None directly; it competes for attention with cash actions.",
            required_action="Open Financial Health and expand this dimension.",
            deadline=None, confidence=0.8,
            explanation="Weight x score gap identifies where effort moves the score most.",
            tags=["health"]))

    recs.sort(key=lambda r: -r.priority)
    return recs
