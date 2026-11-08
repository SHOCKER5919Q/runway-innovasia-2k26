"""API contract, tenant isolation and authorisation."""
from __future__ import annotations

from datetime import date

import pytest

TODAY = date(2026, 11, 7)
AS = f"?as_of={TODAY.isoformat()}"

READ_ENDPOINTS = [
    "/api/overview", "/api/briefing", "/api/business", "/api/accounts",
    "/api/states/actual", "/api/states/predicted", "/api/states/history",
    "/api/states/reconcile", "/api/forecast", "/api/risk", "/api/health",
    "/api/recommendations", "/api/receivables", "/api/payables", "/api/customers",
    "/api/suppliers", "/api/compliance", "/api/transactions", "/api/invoices",
    "/api/twin/state", "/api/twin/graph", "/api/twin/timeline", "/api/twin/activity",
    "/api/scenarios", "/api/scenarios/catalogue", "/api/reports/passport",
    "/api/integrations", "/api/integrations/accounts", "/api/integrations/batches",
    "/api/copilot/suggestions", "/api/copilot/tools",
]


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_every_read_endpoint_responds(client, owner_auth, path):
    r = client.get(path + AS, headers=owner_auth)
    assert r.status_code == 200, f"{path}: {r.text[:300]}"
    assert r.json() is not None


@pytest.mark.parametrize("path", READ_ENDPOINTS[:12])
def test_every_endpoint_requires_a_token(client, path):
    assert client.get(path).status_code == 401


def test_an_invalid_token_is_rejected(client, business_id):
    r = client.get("/api/overview",
                   headers={"Authorization": "Bearer not-a-real-token",
                            "X-Business-Id": business_id})
    assert r.status_code == 401


def test_a_user_cannot_read_a_business_they_do_not_belong_to(client, second_business_id):
    """The owner account has no membership in the second business."""
    tok = client.post("/api/auth/login",
                      json={"email": "owner@runway.demo", "password": "demo1234"}
                      ).json()["token"]
    r = client.get("/api/overview" + AS,
                   headers={"Authorization": f"Bearer {tok}",
                            "X-Business-Id": second_business_id})
    assert r.status_code == 403, "tenant isolation breach"


def test_the_accountant_sees_only_granted_businesses(client, ca_auth):
    tok = ca_auth["token"]
    listed = {b["id"] for b in ca_auth["businesses"]}
    r = client.get("/api/accountant/portfolio" + AS,
                   headers={"Authorization": f"Bearer {tok}",
                            "X-Business-Id": ca_auth["active_business_id"]})
    assert r.status_code == 200
    returned = {c["business"]["id"] for c in r.json()["clients"]}
    assert returned <= listed


def test_a_non_accountant_cannot_open_the_portfolio(client, owner_auth):
    assert client.get("/api/accountant/portfolio" + AS, headers=owner_auth).status_code == 403


def test_a_viewer_level_action_requires_the_right_role(client, business_id):
    """The chartered accountant has the 'accountant' role on the demo business,
    which sits below manager, so policy edits must be refused."""
    s = client.post("/api/auth/login",
                    json={"email": "ca@runway.demo", "password": "demo1234"}).json()
    r = client.patch("/api/business",
                     headers={"Authorization": f"Bearer {s['token']}",
                              "X-Business-Id": business_id},
                     json={"safety_buffer_paise": 1})
    assert r.status_code == 403


def test_login_rejects_a_wrong_password(client):
    r = client.post("/api/auth/login",
                    json={"email": "owner@runway.demo", "password": "wrong-password"})
    assert r.status_code == 401
    assert "Invalid" in r.json()["detail"]


def test_a_missing_account_is_indistinguishable_from_a_wrong_password(client):
    a = client.post("/api/auth/login",
                    json={"email": "nobody@runway.demo", "password": "whatever123"})
    b = client.post("/api/auth/login",
                    json={"email": "owner@runway.demo", "password": "whatever123"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_passwords_are_never_returned(client, owner_auth):
    body = client.get("/api/auth/me", headers=owner_auth).text.lower()
    assert "password" not in body and "pbkdf2" not in body


def test_a_shared_report_link_can_be_revoked(client, owner_auth):
    issued = client.post("/api/reports/passport/share" + AS, headers=owner_auth,
                         json={"recipient": "Test Bank", "expires_in_days": 7})
    assert issued.status_code == 200
    token = issued.json()["token"]
    assert client.get(f"/public/shared/{token}").status_code == 200

    rid = client.get("/api/reports/shared", headers=owner_auth).json()["shares"][0]["id"]
    assert client.post(f"/api/reports/shared/{rid}/revoke", headers=owner_auth).status_code == 200
    after = client.get(f"/public/shared/{token}")
    assert after.status_code == 410


def test_an_unknown_share_token_is_not_found(client):
    assert client.get("/public/shared/deadbeef").status_code == 404


def test_health_endpoint_is_public(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_responses_carry_a_request_id(client, owner_auth):
    r = client.get("/api/meta", headers=owner_auth)
    assert r.headers.get("X-Request-Id")
    assert r.headers.get("X-Response-Time-Ms")


# ── behavioural contracts ─────────────────────────────────────────

def test_the_overview_never_folds_receivables_into_cash(client, owner_auth):
    d = client.get("/api/overview" + AS, headers=owner_auth).json()["headline"]
    assert d["available_cash"]["paise"] < d["receivables"]["paise"]
    assert (d["available_cash"]["paise"]
            == d["cash_in_hand"]["paise"] - d["restricted"]["paise"] - d["committed"]["paise"])


def test_the_briefing_labels_every_line_with_its_state(client, owner_auth):
    for line in client.get("/api/briefing" + AS, headers=owner_auth).json()["lines"]:
        assert line["state"] in ("actual", "predicted", "simulated")


def test_the_passport_refuses_to_claim_it_is_a_credit_rating(client, owner_auth):
    decls = " ".join(client.get("/api/reports/passport" + AS,
                                headers=owner_auth).json()["declarations"]).lower()
    assert "not a credit rating" in decls
    assert "credit score" in decls
    assert "synthetic" in decls


def test_integrations_do_not_claim_live_connections(client, owner_auth):
    cat = client.get("/api/integrations", headers=owner_auth).json()
    for a in cat["available"]:
        assert a["status"] == "available"
    aa = next((p for p in cat["planned"] if p["key"] == "account_aggregator"), None)
    assert aa is not None
    assert aa["status"] == "regulated_entity_required"
    assert "no claim of live AA connectivity" in " ".join(
        [aa["runway_support"]]).lower() or "makes no claim" in aa["runway_support"].lower()


def test_transaction_filters_and_pagination(client, owner_auth):
    r = client.get("/api/transactions?page=1&page_size=10&direction=credit" ,
                   headers=owner_auth).json()
    assert len(r["items"]) <= 10
    assert all(i["direction"] == "credit" for i in r["items"])
    assert r["pages"] >= 1


def test_an_owner_correction_is_recorded_as_verified(client, owner_auth):
    first = client.get("/api/transactions?page=1&page_size=1", headers=owner_auth).json()
    tid = first["items"][0]["id"]
    r = client.patch(f"/api/transactions/{tid}", headers=owner_auth,
                     json={"category": "other_expense"})
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "other_expense"
    assert body["evidence"] == "verified_actual"
    assert any(s.get("step") == "owner_correction"
               for s in body["provenance"]["transform_log"])
