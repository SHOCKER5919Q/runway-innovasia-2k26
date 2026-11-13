"""Copilot orchestration: question -> intent -> tool -> explanation.

The deterministic renderer below is not a stub. It is the default path and
has to be good, because the product must be fully demonstrable with no API
key and because it is the fallback whenever the LLM produces a figure the
tools did not.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.copilot import llm, models, router, tools
from app.core.money import format_inr
from app.models import CopilotMessage, _uid

SUGGESTIONS = [
    "How much cash do I actually have today?",
    "Why is my runway shorter than it looks?",
    "Which customers are delaying payments?",
    "Should I accept a Rs 15 lakh order on 60-day terms?",
    "What if my biggest customer pays 30 days late?",
    "How much should I reserve for GST this month?",
    "Which invoices should I follow up on today?",
    "Can I afford two new employees?",
    "What is my worst-case cash position?",
    "How accurate have your forecasts been?",
]


def ask(db, bundle, question: str, *, conversation_id: str | None = None,
        language: str = "en", user_id: str | None = None,
        use_llm: bool = True, model: str | None = None) -> dict:
    conv = conversation_id or _uid()
    names = [c.name for c in bundle.behaviour] + [s.name for s in bundle.supplier_profiles]
    intent = router.route(question, known_customers=names)

    args = dict(intent.args)
    result = tools.call(intent.tool, bundle, db=db, **args)

    model_id, category = models.resolve(model, intent.tool, language)
    reply, generator = (None, "deterministic")
    if use_llm and llm.available() and model_id != models.BUILTIN:
        reply, generator = llm.explain(question, intent.tool, result,
                                       language=language,
                                       business_name=bundle.business.name,
                                       model=model_id)
    if reply is None:
        reply = render(intent, result, bundle)

    db.add(CopilotMessage(id=_uid(), business_id=bundle.business.id, conversation_id=conv,
                          role="user", content=question[:4000], language=language))
    db.add(CopilotMessage(
        id=_uid(), business_id=bundle.business.id, conversation_id=conv, role="assistant",
        content=reply, tool_calls_json=[{"tool": intent.tool, "args": args,
                                         "state": result.get("state"),
                                         "matched": intent.matched,
                                         "confidence": round(intent.score / 5.0, 2)}],
        evidence_json=result.get("evidence", []),
        state_refs_json={"actual_state_id": bundle.actual_state.id,
                         "actual_version": bundle.actual_state.version,
                         "predicted_state_id": bundle.predicted_state.id,
                         "predicted_version": bundle.predicted_state.version,
                         "as_of": bundle.as_of.isoformat()},
        language=language, generator=generator))
    db.commit()

    return {
        "conversation_id": conv,
        "question": question,
        "answer": reply,
        "generator": generator,
        "model": {"requested": model or models.AUTO,
                  "used": generator.split(":", 1)[1] if generator.startswith("llm:") else models.BUILTIN,
                  "category": category,
                  "category_label": models.CATEGORIES.get(category)},
        "tool": {"name": intent.tool, "args": args, "matched_phrase": intent.matched,
                 "routing_confidence": round(min(1.0, intent.score / 5.0), 2)},
        "state": result.get("state"),
        "state_label": _state_label(result.get("state")),
        "ok": result.get("ok", True),
        "data": result.get("data", {}),
        "evidence": result.get("evidence", []),
        "as_of": result.get("as_of"),
        "state_refs": {"actual_version": bundle.actual_state.version,
                       "predicted_version": bundle.predicted_state.version,
                       "ledger_fingerprint": bundle.actual_state.ledger_fingerprint},
        "followups": intent.followups or _followups(intent.tool),
        "disclaimer": _disclaimer(result.get("state")),
    }


def _state_label(state: str | None) -> str:
    return {"actual": "Actual - recorded in your ledger",
            "predicted": "Predicted - a model estimate with uncertainty",
            "simulated": "Simulated - a what-if, not a record",
            "reconciliation": "Measured accuracy of past forecasts",
            "unavailable": "Not available"}.get(state or "", "")


def _disclaimer(state: str | None) -> str | None:
    if state == "predicted":
        return ("These are simulation quantiles from this business's own ledger, not "
                "guarantees. P10 is a pessimistic path, P90 an optimistic one.")
    if state == "simulated":
        return ("Simulated figures. Nothing here has been written to your ledger and no "
                "action has been taken.")
    return None


def _followups(tool_name: str) -> list[str]:
    return {
        "get_actual_state": ["What does the next 13 weeks look like?",
                             "How much of this is already committed?"],
        "get_cash_runway": ["What is driving the forecast?",
                            "What if my biggest customer pays 30 days late?"],
        "get_receivables": ["Which invoices should I follow up on today?",
                            "What would discounting these cost?"],
        "get_customer_risk": ["What if that customer defaults?",
                              "How concentrated is my customer base?"],
        "get_upcoming_liabilities": ["Can I cover these from expected collections?",
                                     "What if I defer a purchase?"],
        "get_financial_health": ["Which dimension should I fix first?",
                                 "How does my working-capital cycle compare?"],
        "get_recommendations": ["Show me the evidence for the top one",
                                "Simulate the top recommendation"],
    }.get(tool_name, ["What should I do today?", "Show me the 13-week forecast"])


# ───────────────── deterministic natural-language renderer ─────────────────

def render(intent, result: dict, b) -> str:
    if not result.get("ok", True):
        return (f"{result['summary']}\n\nI will not estimate a figure I cannot "
                f"source from your ledger or from a completed forecast run.")

    state = result.get("state")
    data = result.get("data", {})
    ev = result.get("evidence", [])
    head = result["summary"]
    prefix = {"actual": "", "predicted": "", "simulated": "",
              "reconciliation": ""}.get(state, "")

    lines = [prefix + head, ""]

    if intent.tool == "run_scenario":
        cmp = data.get("comparison", {})
        lines.append("Baseline versus this scenario:")
        for r in cmp.get("rows", [])[:6]:
            bv, sv = r["baseline"], r["scenario"]
            if r["unit"] == "paise":
                bv, sv = format_inr(int(bv)), format_inr(int(sv))
            elif r["unit"] == "probability":
                bv, sv = f"{bv:.0%}", f"{sv:.0%}"
            else:
                bv, sv = f"{bv} weeks", f"{sv} weeks"
            lines.append(f"  - {r['metric']}: {bv} -> {sv} ({r['direction']})")
        econ = data.get("economics", {})
        if econ.get("disclaimer"):
            lines += ["", econ["disclaimer"]]
        lines += ["", cmp.get("method", "")]
        lines += ["", "Nothing has been written to your ledger. This is a simulation."]
        return "\n".join(lines)

    if ev:
        lines.append("Evidence:")
        for e in ev[:8]:
            lines.append(f"  - {e['label']}: {e['value']}")

    tail = {
        "get_cash_runway": ("The P10 figure is the one to plan against: it is the path "
                            "where things go moderately wrong, not catastrophically."),
        "get_predicted_state": ("Open Cash Runway to see the band week by week, or the "
                                "Scenario Lab to test a decision against it."),
        "get_receivables": "The collection list is ranked by amount, ageing and customer risk.",
        "get_customer_risk": ("Every figure here comes from settled invoices only - open "
                              "invoices say nothing about how fast someone pays."),
        "get_upcoming_liabilities": ("GST figures marked as an estimate are derived from your "
                                     "ledger, not from a filed return. Confirm on the portal."),
        "get_financial_health": ("This is RUNWAY's own indicator, not a credit score. "
                                 "Every weight is visible and configurable."),
        "get_recommendations": ("Nothing here happens automatically. RUNWAY never pays, "
                                "borrows or commits on your behalf."),
        "get_stress_tests": ("These are severity tests, not predictions. They answer "
                             "'could the business survive this', not 'will this happen'."),
        "evaluate_forecast_accuracy": ("Measured on forecasts whose target week has already "
                                       "passed - nothing here is self-reported."),
    }.get(intent.tool)
    if tail:
        lines += ["", tail]
    return "\n".join(lines)
