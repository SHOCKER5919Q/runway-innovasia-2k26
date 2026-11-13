"""The copilot's model catalogue: which model to use for which analysis.

Every model here only *writes* the explanation. The figures are computed
first by the deterministic tools (``copilot.tools``) and every rupee amount
in a reply is checked against them (``llm.verify_numbers``); a reply with an
unverified figure is discarded and the built-in renderer answers instead. So
a weaker model can make an answer less clear - it cannot make it wrong.

Assignments come from a measured benchmark, not from reputation: 18 free
xkiro models x 10 real questions on the demo ledger (2026-11-13), scored on
verified figures, latency, Flesch reading ease and correct script for Hindi
and Telugu. Samples per category are small (1-3 questions), so treat the
per-category numbers as guidance. Report: docs/COPILOT_MODELS.md.
"""
from __future__ import annotations

AUTO = "auto"
BUILTIN = "builtin"

# Analysis categories, decided from the tool the router picked.
CATEGORY_OF_TOOL = {
    "get_actual_state": "position", "get_cash_position": "position",
    "get_receivables": "position", "get_payables": "position",
    "get_supplier_obligations": "position", "get_upcoming_liabilities": "position",
    "get_transactions_summary": "position", "get_data_quality": "position",
    "get_customer_risk": "position", "get_payment_prediction": "position",
    "get_predicted_state": "forecast", "get_cash_runway": "forecast",
    "get_forecast_drivers": "forecast", "evaluate_forecast_accuracy": "forecast",
    "get_financial_health": "forecast",
    "get_risk_alerts": "risk", "get_stress_tests": "risk",
    "get_concentration_risk": "risk",
    "run_scenario": "decision", "compare_options": "decision",
    "get_recommendations": "decision", "get_scenario_catalogue": "decision",
}

CATEGORIES = {
    "position": "Cash, dues and balances - what is true today",
    "forecast": "Runway, forecast and health - what is likely",
    "risk": "Alerts, stress tests and concentration - what could go wrong",
    "decision": "Scenarios and recommendations - what to do",
    "language": "Answers in Hindi, Telugu, Tamil or Marathi",
}

# id -> catalogue entry. ``bench`` = verified replies / questions answered,
# median seconds, mean Flesch reading ease (English; higher = easier).
MODELS: list[dict] = [
    {"id": "mistralai/mistral-medium-3.5", "label": "Mistral Medium 3.5",
     "tier": "free", "provider": "xkiro",
     "best_for": ["position", "forecast", "risk", "language"],
     "speed": "fast", "readability": "plain English",
     "bench": {"verified": "10/10", "median_s": 1.7, "flesch": 61},
     "summary": "Best all-rounder: every figure verified, the quickest of the accurate "
                "models, and correct Hindi and Telugu script."},
    {"id": "mistralai/mistral-large-2512", "label": "Mistral Large",
     "tier": "free", "provider": "xkiro",
     "best_for": ["decision"],
     "speed": "fast", "readability": "plainest English",
     "bench": {"verified": "10/10", "median_s": 2.1, "flesch": 65},
     "summary": "Most careful on decisions and scenarios, and the easiest to read of "
                "all models tested."},
    {"id": "mistralai/mistral-small-2603", "label": "Mistral Small",
     "tier": "free", "provider": "xkiro",
     "best_for": [],
     "speed": "fastest", "readability": "plain English",
     "bench": {"verified": "9/10", "median_s": 1.5, "flesch": 59},
     "summary": "Quickest replies. Once added two amounts together itself; the "
                "verifier caught it and the built-in answer was shown instead."},
    {"id": "cohere/aya-expanse-32b", "label": "Aya Expanse 32B",
     "tier": "free", "provider": "xkiro",
     "best_for": [],
     "speed": "slow", "readability": "denser",
     "bench": {"verified": "9/10", "median_s": 6.5, "flesch": 42},
     "summary": "Multilingual specialist. Accurate, correct scripts, but slower and "
                "wordier than Mistral Medium."},
    {"id": "cohere/command-r7b-12-2024", "label": "Command R7B",
     "tier": "free", "provider": "xkiro",
     "best_for": [],
     "speed": "medium", "readability": "denser",
     "bench": {"verified": "10/10", "median_s": 2.8, "flesch": 50},
     "summary": "Reliable backup. Long answers, and its Telugu reply was not in "
                "Telugu script - avoid for Indian languages."},
]

# What "Auto" uses for each category.
AUTO_PICK = {
    "position": "mistralai/mistral-medium-3.5",
    "forecast": "mistralai/mistral-medium-3.5",
    "risk": "mistralai/mistral-medium-3.5",
    "decision": "mistralai/mistral-large-2512",
    "language": "mistralai/mistral-medium-3.5",
}

_BY_ID = {m["id"]: m for m in MODELS}


def category_for(tool_name: str, language: str = "en") -> str:
    if language and language != "en":
        return "language"
    return CATEGORY_OF_TOOL.get(tool_name, "position")


def resolve(requested: str | None, tool_name: str, language: str = "en") -> tuple[str, str]:
    """``(model_id, category)``. ``model_id`` is BUILTIN for the offline renderer."""
    cat = category_for(tool_name, language)
    req = (requested or AUTO).strip()
    if req == BUILTIN:
        return BUILTIN, cat
    if req in _BY_ID:
        return req, cat
    return AUTO_PICK[cat], cat


def catalogue(llm_available: bool) -> dict:
    return {
        "default": AUTO,
        "llm_available": llm_available,
        "quota": _quota(),
        "categories": CATEGORIES,
        "auto_pick": AUTO_PICK,
        "options": (
            [{"id": AUTO, "label": "Auto - best model for each question",
              "tier": "free", "summary": "Picks per question using the benchmark: "
              "Mistral Medium for today's figures, forecasts, risk and Indian "
              "languages; Mistral Large for decisions and scenarios."}]
            + (MODELS if llm_available else [])
            + [{"id": BUILTIN, "label": "Built-in (no AI model)", "tier": "free",
                "speed": "instant", "readability": "fixed template",
                "summary": "Works offline. Same figures, plainer wording."}]),
        "guarantee": ("Whichever model you pick, the figures come from RUNWAY's own "
                      "calculations and every rupee amount is checked before it is "
                      "shown. A model can change how clear the answer is, never the "
                      "numbers."),
    }


def _quota() -> dict:
    from app.copilot import llm
    return llm.quota_status()
