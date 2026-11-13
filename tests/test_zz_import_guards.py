"""A file from another account's era is refused; a wrong upload can be undone."""
from __future__ import annotations

from conftest import TODAY

Q = f"?as_of={TODAY.isoformat()}"


def _acc(client, h):
    return next(a["id"] for a in client.get("/api/integrations/accounts", headers=h).json()["accounts"]
                if a["kind"] == "current")


def _imp(client, h, content, dry):
    return client.post("/api/integrations/import" + Q, headers=h,
                       data={"adapter": "bank_csv", "account_id": _acc(client, h),
                             "dry_run": "true" if dry else "false"},
                       files={"file": ("s.csv", content, "text/csv")}).json()


def test_rows_before_the_account_opened_are_refused(client, owner_auth):
    old = b"Date,Narration,Withdrawal (INR),Deposit (INR)\n2010-04-01,Old era,,1000000.00\n"
    r = _imp(client, owner_auth, old, dry=False)
    assert r["rows_imported"] == 0 and r["rows_rejected"] == 1
    assert "before this account was opened" in r["errors"][0]["error"]


def test_a_wrong_upload_can_be_reverted(client, owner_auth):
    h = owner_auth
    cash0 = client.get("/api/overview" + Q, headers=h).json()["headline"]["cash_in_hand"]["paise"]
    f = (f"Date,Narration,Ref,Withdrawal Amt.,Deposit Amt.\n"
         f"{TODAY:%d/%m/%Y},WRONG FILE TEST CREDIT,WRONG-1,,5000000.00\n").encode()
    r = _imp(client, h, f, dry=False)
    assert r["rows_imported"] == 1
    assert client.get("/api/overview" + Q, headers=h).json()["headline"]["cash_in_hand"]["paise"] \
        == cash0 + 500000000
    rv = client.post(f"/api/integrations/batches/{r['batch_id']}/revert" + Q, headers=h)
    assert rv.status_code == 200 and rv.json()["transactions_removed"] == 1
    assert client.get("/api/overview" + Q, headers=h).json()["headline"]["cash_in_hand"]["paise"] == cash0
    assert client.post(f"/api/integrations/batches/{r['batch_id']}/revert" + Q,
                       headers=h).status_code == 409
    b = next(x for x in client.get("/api/integrations/batches", headers=h).json()["batches"]
             if x["id"] == r["batch_id"])
    assert b["status"] == "reverted"          # kept in history
