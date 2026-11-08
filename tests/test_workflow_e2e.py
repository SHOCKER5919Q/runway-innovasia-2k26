"""The signature end-to-end story, asserted step by step.

A business imports data, RUNWAY reconciles it, discovers a slow payer,
projects the consequence, is asked to evaluate a decision, and recommends
an action — without ever moving money.
"""
from __future__ import annotations

from datetime import date

import pytest

TODAY = date(2026, 11, 7)
AS = f"?as_of={TODAY.isoformat()}"


def test_01_import_a_bank_statement_with_a_duplicate(client, owner_auth):
    acc = client.get("/api/integrations/accounts", headers=owner_auth).json()["accounts"][0]["id"]
    sample = client.get("/api/integrations/sample/bank_csv").json()
    r = client.post("/api/integrations/import" + AS, headers=owner_auth,
                    data={"adapter": "bank_csv", "account_id": acc, "dry_run": "true"},
                    files={"file": ("hdfc.csv", sample["content"].encode(), "text/csv")})
    assert r.status_code == 200
    b = r.json()
    assert b["rows_seen"] == 5
    assert b["duplicates_rejected"] == 1, "the repeated row must be caught"
    assert b["dry_run"] is True
    cats = {p.get("category") for p in b["preview"] if p["kind"] == "transaction"}
    assert "gst_payment" in cats and "customer_receipt" in cats


def test_02_the_ledger_produces_a_real_cash_position(client, owner_auth):
    d = client.get("/api/states/actual" + AS, headers=owner_auth).json()
    assert d["cash"]["paise"] > 0
    assert d["receivables"]["paise"] > 0
    total = sum(a["closing_paise"] for a in d["accounts"])
    assert total == d["cash"]["paise"]


def test_03_a_slow_payer_is_identified_from_settled_invoices(client, owner_auth):
    cs = client.get("/api/customers" + AS, headers=owner_auth).json()["customers"]
    risky = [c for c in cs if c["risk_band"] in ("high", "critical")]
    assert risky, "scenario B should surface at least one high-risk buyer"
    worst = max(cs, key=lambda c: c["mean_delay_days"])
    assert worst["invoices_settled"] > 10
    assert worst["mean_delay_days"] > 5
    assert worst["evidence"]


def test_04_the_forecast_has_calibrated_bands(client, owner_auth):
    s = client.get("/api/states/predicted" + AS, headers=owner_auth).json()["series"]
    assert len(s["p50"]) == s["horizon_weeks"] + 1
    for i in range(len(s["p50"])):
        assert s["p10"][i] <= s["p50"][i] <= s["p90"][i]
    assert s["paths"] >= 100, "the forecast must be a real simulation, not a single path"


def test_05_the_risk_engine_explains_itself(client, owner_auth):
    alerts = client.get("/api/risk" + AS, headers=owner_auth).json()["alerts"]
    assert alerts
    for a in alerts:
        for field in ("what_happened", "why_it_matters", "recommended_action", "if_ignored"):
            assert a[field], f"{a['code']} is missing {field}"
        assert isinstance(a["evidence"], list)


def test_06_stress_tests_say_what_the_business_cannot_survive(client, owner_auth):
    tests = client.get("/api/risk" + AS, headers=owner_auth).json()["stress_tests"]
    assert len(tests) >= 6
    keys = {t["key"] for t in tests}
    assert {"largest_customer_default", "revenue_drop_20", "compound_shock"} <= keys
    for t in tests:
        assert isinstance(t["survives"], bool)
        assert t["description"] and t["severity"] in ("moderate", "severe", "extreme")
    # The shocks that act on money already owed must unambiguously hurt.
    for key in ("largest_customer_default", "receivables_delay_30", "compound_shock"):
        t = next(x for x in tests if x["key"] == key)
        assert t["min_cash_delta_paise"] < 0, key


def test_07_the_simulator_evaluates_the_signature_decision(client, owner_auth):
    r = client.post("/api/scenarios/quick-run" + AS, headers=owner_auth, json={
        "kind": "new_order",
        "parameters": {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                       "advance_pct": 0.0, "credit_days": 60},
        "paths": 1200})
    assert r.status_code == 200
    b = r.json()
    econ = b["economics"]
    assert econ["expected_revenue_paise"] == 15_00_000_00
    assert econ["funding_gap_days"] > 0, "the order must show a funding gap, not just profit"
    assert econ["cash_out_before_cash_in_paise"] > 0
    assert b["saved"] is False
    assert "ledger" in b["isolation_guarantee"].lower()


def test_08_an_advance_measurably_improves_the_same_order(client, owner_auth):
    def run(advance):
        return client.post("/api/scenarios/quick-run" + AS, headers=owner_auth, json={
            "kind": "new_order",
            "parameters": {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                           "advance_pct": advance, "credit_days": 60},
            "paths": 1500}).json()
    a, b = run(0.0), run(0.30)
    assert (b["comparison"]["rows"][0]["scenario"] > a["comparison"]["rows"][0]["scenario"]), \
        "a 30% advance must improve minimum cash"
    assert b["comparison"]["breach_delta"] <= a["comparison"]["breach_delta"]
    assert "common random numbers" in b["comparison"]["method"]


def test_09_the_optimiser_ranks_options_and_flags_policy_breaches(client, owner_auth):
    r = client.post("/api/scenarios/optimise" + AS, headers=owner_auth, json={
        "options": [
            {"key": "A", "label": "Accept, no advance", "kind": "new_order",
             "params": {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                        "advance_pct": 0.0, "credit_days": 60}},
            {"key": "B", "label": "Accept with 30% advance", "kind": "new_order",
             "params": {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                        "advance_pct": 0.30, "credit_days": 60}},
            {"key": "C", "label": "Discount receivables", "kind": "invoice_discounting",
             "params": {"max_amount_paise": 10_00_000_00}},
        ],
        "paths": 1000})
    assert r.status_code == 200
    d = r.json()
    assert len(d["options"]) == 3
    assert d["caveat"] and "owner decides" in d["caveat"].lower()
    for o in d["options"]:
        assert "terms" in o or "error" in o
        if o.get("feasible") is False:
            assert o["policy_violations"]


def test_10_a_saved_scenario_pins_its_baseline(client, owner_auth):
    created = client.post("/api/scenarios" + AS, headers=owner_auth, json={
        "name": "E2E — accept the order", "kind": "new_order",
        "parameters": {"order_value_paise": 15_00_000_00, "margin_pct": 0.18,
                       "advance_pct": 0.0, "credit_days": 60}}).json()
    sid = created["scenario"]["id"]
    assert created["baseline_state_ids"]["actual"]
    assert created["isolation_guarantee"]

    again = client.post(f"/api/scenarios/{sid}/run" + AS, headers=owner_auth).json()
    assert again["baseline_state_ids"] == created["baseline_state_ids"], \
        "a re-run must use the baseline the scenario was created against"


def test_11_recommendations_are_evidenced_and_need_approval(client, owner_auth):
    d = client.get("/api/recommendations" + AS, headers=owner_auth).json()
    assert d["recommendations"]
    for r in d["recommendations"]:
        assert r["evidence"], r["code"]
        assert r["explanation"], r["code"]
        assert r["downside"], r["code"]
        assert set(["urgency", "impact", "confidence", "ease", "reversibility"]) \
            <= set(r["score_terms"].keys())
    assert "never executes" in d["guarantee"].lower()
    borrow = [r for r in d["recommendations"] if r["code"] == "close_liquidity_gap"]
    if borrow:
        opts = borrow[0]["score_terms"]["funding_options"]
        assert any("Collect overdue" in o["option"] for o in opts), \
            "free liquidity must be offered before borrowing"
        assert opts[0]["cost_paise"] <= opts[-1]["cost_paise"]


def test_12_a_decision_can_be_recorded_without_touching_the_ledger(client, owner_auth):
    sid = client.get("/api/scenarios", headers=owner_auth).json()["scenarios"][0]["id"]
    before = client.get("/api/states/actual" + AS, headers=owner_auth).json()["cash"]["paise"]
    r = client.post(f"/api/scenarios/{sid}/decision", headers=owner_auth,
                    json={"status": "implemented", "implementation_date": TODAY.isoformat(),
                          "note": "Accepted after review"})
    assert r.status_code == 200
    assert "No ledger entry" in r.json()["note"]
    after = client.get("/api/states/actual" + AS, headers=owner_auth).json()["cash"]["paise"]
    assert after == before


def test_13_the_passport_separates_verified_from_estimated(client, owner_auth):
    p = client.get("/api/reports/passport" + AS, headers=owner_auth).json()
    kinds = {s["verification"] for s in p["sections"]}
    assert "verified_actual" in kinds
    assert "model_prediction" in kinds
    acc = next(s for s in p["sections"] if s["key"] == "forecast_accuracy")
    assert isinstance(acc["value"], list)


def test_14_the_copilot_explains_a_prediction_with_its_drivers(client, owner_auth):
    b = client.post("/api/copilot/ask" + AS, headers=owner_auth,
                    json={"question": "Which customers are delaying payments?"}).json()
    assert b["state"] == "actual"
    assert b["evidence"]
    assert any("settled invoices analysed" in e["value"] for e in b["evidence"])


def test_15_forecast_accuracy_is_measured_not_claimed(client, owner_auth):
    d = client.get("/api/states/reconcile" + AS, headers=owner_auth).json()
    assert "note" in d
    if d["available"]:
        for h in d["cash_forecast_by_horizon"]:
            assert h["n"] > 0
            assert 0.0 <= h["p10_p90_coverage"] <= 1.0
            assert h["coverage_target"] == 0.80
        assert d["interpretation"]
    else:
        assert "has not measured" in d["interpretation"]
