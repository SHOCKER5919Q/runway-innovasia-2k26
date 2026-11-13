"""Role sign-up and the approval chain.

manager    -> owner must approve
accountant -> manager AND owner must approve
Nothing in the business is readable until the chain is complete.
"""
from __future__ import annotations

from conftest import AS_OF

PW = "s3cure-pass-1"


def _register(client, email, role, *, join_code=None, business_name=None):
    body = {"email": email, "password": PW, "full_name": email.split("@")[0], "role": role}
    if join_code:
        body["join_code"] = join_code
    if business_name:
        body["business_name"] = business_name
    return client.post("/api/auth/register", json=body)


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()


def _hdr(token, business_id):
    return {"Authorization": f"Bearer {token}", "X-Business-Id": business_id}


def _manager_auth(client, business_id):
    r = client.post("/api/auth/login",
                    json={"email": "manager@runway.demo", "password": "demo1234"})
    return _hdr(r.json()["token"], business_id)


def _request_id(client, owner_auth, email):
    team = client.get("/api/team", headers=owner_auth).json()
    return next(m["membership_id"] for m in team["requests"] if m["email"] == email)


def test_owner_sees_join_code(client, owner_auth):
    r = client.get("/api/team", headers=owner_auth)
    assert r.status_code == 200
    assert r.json()["join_code"].startswith("RW-")


def test_unknown_join_code_is_refused(client):
    r = _register(client, "nobody@example.com", "manager", join_code="RW-NOPE0000")
    assert r.status_code == 422


def test_manager_needs_owner_and_sees_nothing_until_then(client, owner_auth, business_id):
    code = client.get("/api/team", headers=owner_auth).json()["join_code"]
    r = _register(client, "mgr2@example.com", "manager", join_code=code)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["businesses"] == []                       # no business opens yet
    assert s["pending_memberships"][0]["waiting_for"] == ["owner"]
    tok = s["token"]
    blocked = client.get("/api/overview" + AS_OF, headers=_hdr(tok, business_id))
    assert blocked.status_code == 403
    assert "approval" in blocked.json()["detail"]

    mid = _request_id(client, owner_auth, "mgr2@example.com")
    # The existing manager cannot approve another manager.
    r = client.post(f"/api/team/{mid}/approve", headers=_manager_auth(client, business_id))
    assert r.status_code == 403
    r = client.post(f"/api/team/{mid}/approve", headers=owner_auth)
    assert r.status_code == 200 and r.json()["status"] == "approved"

    tok = _login(client, "mgr2@example.com")["token"]
    assert client.get("/api/overview" + AS_OF, headers=_hdr(tok, business_id)).status_code == 200


def test_accountant_needs_manager_and_owner(client, owner_auth, business_id):
    code = client.get("/api/team", headers=owner_auth).json()["join_code"]
    assert _register(client, "ca2@example.com", "accountant", join_code=code).status_code == 201
    mid = _request_id(client, owner_auth, "ca2@example.com")

    r = client.post(f"/api/team/{mid}/approve", headers=owner_auth)
    assert r.json() == {"membership_id": mid, "status": "pending", "waiting_for": ["manager"]}
    tok = _login(client, "ca2@example.com")["token"]
    assert client.get("/api/overview" + AS_OF, headers=_hdr(tok, business_id)).status_code == 403
    # The owner cannot approve twice to skip the manager.
    assert client.post(f"/api/team/{mid}/approve", headers=owner_auth).status_code == 403

    r = client.post(f"/api/team/{mid}/approve", headers=_manager_auth(client, business_id))
    assert r.json()["status"] == "approved"
    assert client.get("/api/overview" + AS_OF, headers=_hdr(tok, business_id)).status_code == 200


def test_one_rejection_ends_the_request(client, owner_auth, business_id):
    code = client.get("/api/team", headers=owner_auth).json()["join_code"]
    _register(client, "ca3@example.com", "accountant", join_code=code)
    mid = _request_id(client, owner_auth, "ca3@example.com")
    r = client.post(f"/api/team/{mid}/reject", headers=_manager_auth(client, business_id))
    assert r.json()["status"] == "rejected"
    assert client.post(f"/api/team/{mid}/approve", headers=owner_auth).status_code == 403
    tok = _login(client, "ca3@example.com")["token"]
    assert client.get("/api/overview" + AS_OF, headers=_hdr(tok, business_id)).status_code == 403


def test_pending_user_cannot_list_team_or_approve(client, owner_auth, business_id):
    code = client.get("/api/team", headers=owner_auth).json()["join_code"]
    s = _register(client, "mgr4@example.com", "manager", join_code=code).json()
    h = _hdr(s["token"], business_id)
    assert client.get("/api/team", headers=h).status_code == 403
    mid = _request_id(client, owner_auth, "mgr4@example.com")
    assert client.post(f"/api/team/{mid}/approve", headers=h).status_code == 403


def test_rotating_the_code_retires_the_old_one(client, owner_auth):
    old = client.get("/api/team", headers=owner_auth).json()["join_code"]
    new = client.post("/api/team/join-code/rotate", headers=owner_auth).json()["join_code"]
    assert new != old
    assert _register(client, "late@example.com", "manager", join_code=old).status_code == 422
    assert _register(client, "late@example.com", "manager", join_code=new).status_code == 201


def test_business_without_a_manager_owner_alone_approves_accountant(client):
    s = _register(client, "solo-owner@example.com", "owner", business_name="Solo Traders")
    assert s.status_code == 201
    owner = s.json()
    biz = owner["businesses"][0]["id"]
    oh = _hdr(owner["token"], biz)
    code = client.get("/api/team", headers=oh).json()["join_code"]
    _register(client, "solo-ca@example.com", "accountant", join_code=code)
    team = client.get("/api/team", headers=oh).json()
    req = next(m for m in team["requests"] if m["email"] == "solo-ca@example.com")
    assert req["required"] == ["owner"]          # no manager exists to ask
    r = client.post(f"/api/team/{req['membership_id']}/approve", headers=oh)
    assert r.json()["status"] == "approved"
    approved = next(m for m in client.get("/api/team", headers=oh).json()["members"]
                    if m["email"] == "solo-ca@example.com")
    assert "no approved manager" in approved["approvals"][0]["covers"]


def test_owner_registration_needs_a_business_name(client):
    assert _register(client, "x@example.com", "owner").status_code == 422
