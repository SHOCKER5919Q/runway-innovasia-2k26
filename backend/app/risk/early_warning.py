"""The early-warning engine.

Every detector returns a fully-formed alert answering the six questions the
specification requires: what happened, why it matters, what evidence
supports it, the likely financial impact, what to do, and what happens if
nothing is done.

Detectors are pure functions of the state bundle so they can be unit-tested
without a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.enums import AlertLevel
from app.core.money import format_inr


@dataclass
class Finding:
    code: str
    level: str
    title: str
    what_happened: str
    why_it_matters: str
    evidence: list[dict]
    impact_paise: int
    impact_date: date | None
    recommended_action: str
    if_ignored: str
    dedupe_key: str = ""
    extra: dict = field(default_factory=dict)


def _d(d: date | None) -> str:
    return d.strftime("%-d %b %Y") if d else "-"


def evaluate(*, business, as_of: date, position, simulation, behaviour, ageing_ar,
             concentration, obligations, coverage, msmed, anomalies,
             health, supplier_profiles) -> list[Finding]:
    f: list[Finding] = []
    buffer = business.safety_buffer_paise

    # ── 1. forecast buffer breach ──────────────────────────────────
    if simulation and simulation.breach_probability >= 0.10:
        wk = simulation.first_breach_week_p50
        when = date.fromisoformat(simulation.week_starts[wk]) if wk else None
        p = simulation.breach_probability
        level = (AlertLevel.CRITICAL if p >= 0.5 else
                 AlertLevel.WARNING if p >= 0.25 else AlertLevel.WATCH)
        f.append(Finding(
            code="forecast_buffer_breach", level=level,
            title=f"Cash may fall below your safety buffer in week {wk}",
            what_happened=(
                f"Across {simulation.paths:,} simulated cash paths, {p:.0%} fall below your "
                f"{format_inr(buffer)} safety buffer at some point in the next "
                f"{simulation.horizon_weeks} weeks. The median first breach is week {wk}"
                + (f" (around {_d(when)})." if when else ".")),
            why_it_matters=(
                "The safety buffer is what lets you absorb a late payment without "
                "missing payroll or a statutory deadline. Once it is gone, every "
                "subsequent decision is forced rather than chosen."),
            evidence=[
                {"label": "Breach probability", "value": f"{p:.0%}"},
                {"label": "Minimum cash (P10)", "value": format_inr(simulation.min_cash_p10_paise)},
                {"label": "Minimum cash (P50)", "value": format_inr(simulation.min_cash_p50_paise)},
                {"label": "Runway P10 / P50", "value": f"{simulation.runway_weeks_p10} / {simulation.runway_weeks_p50} weeks"},
                {"label": "Liquidity VaR (95%)", "value": format_inr(simulation.liquidity_var_paise)},
            ],
            impact_paise=max(0, buffer - simulation.min_cash_p10_paise),
            impact_date=when,
            recommended_action=(
                "Open the Scenario Lab and compare: accelerating your three largest "
                "overdue collections, deferring any non-contractual purchase, and "
                "arranging standby working capital."),
            if_ignored=(
                "A single further payment slip would turn a manageable gap into a "
                "missed payroll or GST deadline, which costs interest, penalty and "
                "supplier goodwill."),
            dedupe_key=f"breach:{wk}"))

    # ── 2. payroll / statutory shortfall ───────────────────────────
    if coverage["shortfall_paise"] > 0:
        f.append(Finding(
            code="obligation_shortfall", level=AlertLevel.CRITICAL,
            title="Upcoming obligations exceed liquidity plus expected collections",
            what_happened=(
                f"Over the next {coverage['horizon_days']} days {format_inr(coverage['total_paise'])} "
                f"falls due. Available liquidity of {format_inr(coverage['available_liquidity_paise'])} "
                f"plus expected collections of {format_inr(coverage['expected_collections_paise'])} "
                f"leaves a gap of {format_inr(coverage['shortfall_paise'])}."),
            why_it_matters=(
                "Payroll and statutory dues are not deferrable. GST paid late attracts "
                "interest at 18% a year plus a late fee, and repeated delays affect "
                "your compliance rating."),
            evidence=[
                {"label": "Obligations due", "value": format_inr(coverage["total_paise"])},
                {"label": "of which statutory", "value": format_inr(coverage["statutory_paise"])},
                {"label": "Coverage (cash only)", "value": f"{coverage['coverage_ratio_cash_only']:.2f}x"},
                {"label": "Coverage with expected collections", "value": f"{coverage['coverage_ratio']:.2f}x"},
                {"label": "With overdraft", "value": f"{coverage['with_overdraft_ratio']:.2f}x"},
            ],
            impact_paise=coverage["shortfall_paise"], impact_date=None,
            recommended_action=(
                "Ring-fence the statutory amount today, then close the remainder by "
                "collection or by drawing on sanctioned working capital."),
            if_ignored="Interest, penalty and a compliance record that follows the business.",
            dedupe_key="obligation_shortfall"))

    # ── 3. receivables ageing deterioration ────────────────────────
    beyond60 = sum(b["amount_paise"] for b in ageing_ar["buckets"][3:])
    if ageing_ar["total_paise"] and beyond60 / ageing_ar["total_paise"] > 0.08:
        share = beyond60 / ageing_ar["total_paise"]
        f.append(Finding(
            code="receivables_ageing", level=AlertLevel.WARNING if share > 0.15 else AlertLevel.WATCH,
            title=f"{share:.0%} of receivables are more than 60 days past due",
            what_happened=(f"{format_inr(beyond60)} of the {format_inr(ageing_ar['total_paise'])} "
                           f"receivables book has aged beyond 60 days past its due date."),
            why_it_matters=("Recovery rates fall sharply after 90 days. Money in the 60+ "
                            "buckets is already funding someone else's working capital."),
            evidence=[{"label": b["label"], "value": format_inr(b["amount_paise"]) + f" ({b['count']})"}
                      for b in ageing_ar["buckets"]],
            impact_paise=beyond60, impact_date=None,
            recommended_action="Work the prioritised collection list from the top down this week.",
            if_ignored="Each month of further ageing materially reduces the chance of full recovery.",
            dedupe_key="ageing_60"))

    # ── 4. per-customer deterioration ──────────────────────────────
    for c in behaviour[:8]:
        if c.risk_band in ("high", "critical") and c.outstanding_paise > 0:
            lvl = AlertLevel.WARNING if c.risk_band == "critical" else AlertLevel.WATCH
            f.append(Finding(
                code="customer_payment_risk", level=lvl,
                title=f"{c.name} is paying {c.mean_delay_days:+.0f} days beyond terms",
                what_happened=(
                    f"{c.name} holds {format_inr(c.outstanding_paise)} of open invoices, "
                    f"{format_inr(c.overdue_paise)} of it overdue, with the oldest "
                    f"{c.oldest_overdue_days} days past due. Across {c.invoices_settled} "
                    f"settled invoices their mean delay is {c.mean_delay_days:+.1f} days "
                    f"(median {c.median_delay_days:+.1f})."),
                why_it_matters=(
                    f"This customer is {c.revenue_share:.0%} of billed revenue. Their payment "
                    f"behaviour drives a large share of the uncertainty in your forecast."),
                evidence=([{"label": "Reliability score", "value": f"{c.reliability_score}/100"},
                           {"label": "On-time rate", "value": f"{c.on_time_rate:.0%}"},
                           {"label": "Outstanding", "value": format_inr(c.outstanding_paise)},
                           {"label": "DSO", "value": f"{c.dso_days} days" if c.dso_days else "-"}]
                          + [{"label": "Basis", "value": e} for e in c.evidence]),
                impact_paise=c.overdue_paise, impact_date=None,
                recommended_action=(
                    f"Call their accounts department and secure a dated commitment. "
                    f"Consider tightening terms on new orders until the ageing clears."),
                if_ignored=("Exposure keeps growing on a buyer who is already slow, which is "
                            "how a receivables problem becomes a bad debt."),
                dedupe_key=f"customer_risk:{c.counterparty_id}"))

    # ── 5. concentration ───────────────────────────────────────────
    if concentration["top1_share"] > business.max_customer_concentration:
        top = concentration["top_counterparties"][0]
        f.append(Finding(
            code="customer_concentration", level=AlertLevel.WARNING,
            title=f"{top['name']} is {top['share']:.0%} of revenue, above your {business.max_customer_concentration:.0%} limit",
            what_happened=(f"Over the last 12 months {top['name']} accounted for "
                           f"{format_inr(top['volume_paise'])} of billing. The book is equivalent "
                           f"to only {concentration['effective_counterparties']} equally-sized customers."),
            why_it_matters=("Losing or being squeezed by a single buyer at this share would "
                            "remove more revenue than the business can absorb from reserves."),
            evidence=[{"label": "HHI", "value": f"{concentration['counterparty_hhi']:.3f} ({concentration['counterparty_band']})"},
                      {"label": "Top 3 share", "value": f"{concentration['top3_share']:.0%}"},
                      {"label": "Sector HHI", "value": f"{concentration['sector_hhi']:.3f}"}],
            impact_paise=top["outstanding_paise"], impact_date=None,
            recommended_action=("Run the 'largest customer defaults' stress test, then set a "
                                "credit limit for this buyer and develop two mid-sized accounts."),
            if_ignored="A single counterparty event becomes an existential event.",
            dedupe_key="concentration"))

    # ── 6. MSMED / 43B(h) ──────────────────────────────────────────
    if msmed["already_breached_paise"] > 0 or msmed["due_within_14_days_paise"] > 0:
        breached = msmed["already_breached_paise"]
        f.append(Finding(
            code="msmed_43bh_exposure",
            level=AlertLevel.WARNING if breached > 0 else AlertLevel.WATCH,
            title=("Payments to micro/small suppliers are past the statutory window"
                   if breached else "Micro/small supplier payments fall due within 14 days"),
            what_happened=(
                f"{format_inr(breached)} is already past the MSMED s.15 deadline and "
                f"{format_inr(msmed['due_within_14_days_paise'])} falls due within 14 days, "
                f"across {len(msmed['items'])} invoices."),
            why_it_matters=(
                "Under Income-tax s.43B(h) an amount owed to a registered micro or small "
                "enterprise is only deductible in the year it is actually paid, and paying "
                "before the return due date does not rescue the earlier year."),
            evidence=([{"label": i["invoice_no"], "value": f"{i['supplier']} - {format_inr(i['amount_paise'])} "
                                                           f"by {i['statutory_deadline']}"}
                       for i in msmed["items"][:6]]
                      + [{"label": "Rule", "value": msmed["rule"]},
                         {"label": "Caveat", "value": msmed["caveat"]}]),
            impact_paise=breached + msmed["due_within_14_days_paise"], impact_date=None,
            recommended_action=("Prioritise these invoices in this week's payment run and "
                                "confirm each supplier's Udyam registration."),
            if_ignored="The expense is disallowed for the year, raising taxable profit.",
            dedupe_key="msmed"))

    # ── 7. anomalies worth an alert ────────────────────────────────
    for a in anomalies:
        if a["severity"] not in ("warning", "critical"):
            continue
        f.append(Finding(
            code=f"anomaly_{a['kind']}", level=AlertLevel.WARNING,
            title={"possible_duplicate_payment": "Possible duplicate payment detected",
                   "amount_outlier": "Unusually large transaction",
                   "spend_shift": "Spending pattern has shifted"}.get(a["kind"], "Anomaly detected"),
            what_happened=a["why"],
            why_it_matters=("Unreviewed anomalies are where money leaks and where a "
                            "reconciliation error becomes a wrong forecast."),
            evidence=[{"label": "Date", "value": a["date"]},
                      {"label": "Amount", "value": format_inr(a["amount_paise"])},
                      {"label": "Category", "value": a["category"]},
                      {"label": "Counterparty", "value": a.get("counterparty") or "unidentified"},
                      {"label": "Narration", "value": a["narration"]}],
            impact_paise=a["amount_paise"], impact_date=date.fromisoformat(a["date"]),
            recommended_action="Open the transaction and confirm or correct it.",
            if_ignored="A duplicate payment stays unrecovered and the ledger stays wrong.",
            dedupe_key=f"anomaly:{a.get('transaction_id') or a['kind']}:{a['date']}"))

    # ── 8. supplier concentration ──────────────────────────────────
    for s in supplier_profiles[:5]:
        if s.concentration_flag:
            f.append(Finding(
                code="supplier_concentration", level=AlertLevel.WATCH,
                title=f"{s.name} supplies {s.spend_share:.0%} of your purchases",
                what_happened=(f"{format_inr(s.lifetime_spend_paise)} of purchases over the last "
                               f"18 months came from {s.name}, with {format_inr(s.outstanding_paise)} "
                               f"currently open."),
                why_it_matters=("A single supplier at this share can dictate price or terms, "
                                "and a disruption there stops your own deliveries."),
                evidence=[{"label": "Spend share", "value": f"{s.spend_share:.0%}"},
                          {"label": "Open balance", "value": format_inr(s.outstanding_paise)},
                          {"label": "Mean days to pay", "value": f"{s.mean_days_to_pay:.0f}"}],
                impact_paise=s.outstanding_paise, impact_date=None,
                recommended_action="Qualify a second source for the top two SKUs from this supplier.",
                if_ignored="You carry their operational risk without any compensation for it.",
                dedupe_key=f"supplier_conc:{s.counterparty_id}"))

    # ── 9. unreviewed early-payment discount ───────────────────────
    for s in supplier_profiles:
        if s.discount_opportunity_paise > 0 and s.discount_annualised_return:
            beats = s.discount_annualised_return > business.max_borrowing_apr
            f.append(Finding(
                code="early_payment_discount", level=AlertLevel.INFO,
                title=f"Early-payment discount available from {s.name}",
                what_happened=(f"{s.name} offers {s.early_discount_pct:.1%} for payment within "
                               f"{s.early_discount_days} days. On currently eligible invoices "
                               f"that is {format_inr(s.discount_opportunity_paise)}."),
                why_it_matters=(f"Taking the discount is equivalent to a "
                                f"{s.discount_annualised_return:.1%} annualised return on the "
                                f"cash used, against your {business.max_borrowing_apr:.0%} "
                                f"borrowing cost ceiling."),
                evidence=[{"label": "Discount", "value": f"{s.early_discount_pct:.2%}"},
                          {"label": "Annualised equivalent", "value": f"{s.discount_annualised_return:.1%}"},
                          {"label": "Eligible amount", "value": format_inr(s.discount_opportunity_paise)}],
                impact_paise=s.discount_opportunity_paise, impact_date=None,
                recommended_action=("Take the discount only if the forecast shows the cash is "
                                    "spare in that week - run it in the Scenario Lab first."
                                    if beats else
                                    "The annualised return is below your borrowing cost; keep the credit period."),
                if_ignored="A risk-free return on idle cash is left on the table." if beats
                           else "No action needed.",
                dedupe_key=f"discount:{s.counterparty_id}"))

    # ── 10. health score deterioration ─────────────────────────────
    weakest = min(health["subscores"], key=lambda s: s["score"])
    if weakest["score"] < 40:
        f.append(Finding(
            code="health_weak_dimension", level=AlertLevel.WATCH,
            title=f"{weakest['label']} is the weakest part of your financial health",
            what_happened=(f"{weakest['label']} scores {weakest['score']}/100 "
                           f"({weakest['band']}), pulling the overall score of "
                           f"{health['score']} down by its {weakest['weight']:.0%} weight."),
            why_it_matters="This is the dimension where improvement moves the score most.",
            evidence=[{"label": "Detail", "value": e} for e in weakest["evidence"]],
            impact_paise=0, impact_date=None,
            recommended_action="Open Financial Health and expand this dimension for the drivers.",
            if_ignored="The weakness compounds into the other dimensions over time.",
            dedupe_key=f"health_weak:{weakest['key']}"))

    order = {AlertLevel.CRITICAL: 0, AlertLevel.WARNING: 1, AlertLevel.WATCH: 2, AlertLevel.INFO: 3}
    f.sort(key=lambda x: (order[x.level], -x.impact_paise))
    return f
