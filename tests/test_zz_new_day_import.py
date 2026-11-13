"""A new day's bank statement flows through to the supplier pages.

Named ``test_zz_`` so it runs last: it changes the shared demo ledger by
paying a real overdue supplier invoice, and earlier tests read that ledger
as seeded.

What is checked, end to end through the HTTP API:
1. The import adds exactly one row, matched to the right purchase invoice.
2. The supplier's outstanding and the business's payables drop by exactly
   the amount paid; the MSMED breach on that invoice clears.
3. The upload is kept in import history with its before/after figures.
4. Uploading the same file again adds nothing - the ledger is append-only and
   a repeat is a duplicate, never a second payment.
5. The earlier day's figures are unchanged when asked for as of that day.
"""
from __future__ import annotations

from datetime import date, timedelta

from conftest import TODAY

NEXT_DAY = TODAY + timedelta(days=1)
Q0 = f"?as_of={TODAY.isoformat()}"
Q1 = f"?as_of={NEXT_DAY.isoformat()}"


def _overdue_msme_invoice(client, h):
    s = client.get("/api/suppliers" + Q0, headers=h).json()
    item = next(i for i in s["msmed"]["items"] if i["days_remaining"] < 0)
    supplier = next(x for x in s["suppliers"] if x["name"] == item["supplier"])
    return item, supplier, s


def _csv(item) -> bytes:
    rupees = item["amount_paise"] / 100
    return ("Date,Narration,Chq./Ref.No.,Withdrawal Amt.,Deposit Amt.\n"
            f"{NEXT_DAY:%d/%m/%Y},NEFT DR {item['supplier']} {item['invoice_no']},"
            f"NEFTN{NEXT_DAY:%Y%m%d}77,{rupees:.2f},\n").encode()


def _import(client, h, content: bytes):
    acc = client.get("/api/integrations/accounts", headers=h).json()["accounts"][0]["id"]
    return client.post("/api/integrations/import" + Q1, headers=h,
                       data={"adapter": "bank_csv", "account_id": acc, "dry_run": "false"},
                       files={"file": ("statement-next-day.csv", content, "text/csv")})


def test_new_day_payment_updates_supplier_pages_and_history(client, owner_auth):
    h = owner_auth
    item, supplier, _ = _overdue_msme_invoice(client, h)
    before = client.get("/api/suppliers" + Q1, headers=h).json()
    sup_before = next(x for x in before["suppliers"] if x["name"] == item["supplier"])
    pay_before = client.get("/api/overview" + Q1, headers=h).json()["headline"]["payables"]["paise"]
    paid = item["amount_paise"]

    r = _import(client, h, _csv(item))
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["rows_imported"] == 1

    after = client.get("/api/suppliers" + Q1, headers=h).json()
    sup_after = next(x for x in after["suppliers"] if x["name"] == item["supplier"])
    assert sup_before["outstanding_paise"] - sup_after["outstanding_paise"] == paid
    assert all(i["invoice_no"] != item["invoice_no"] for i in after["msmed"]["items"])
    pay_after = client.get("/api/overview" + Q1, headers=h).json()["headline"]["payables"]["paise"]
    assert pay_before - pay_after == paid

    # 3. kept in history with what it changed
    batches = client.get("/api/integrations/batches", headers=h).json()["batches"]
    mine = next(b for b in batches if b["id"] == res["batch_id"])
    changes = {c["key"]: c for c in mine["impact"]["changes"]}
    assert changes["payables_paise"]["change"] == -paid
    assert changes["transactions"]["change"] == 1
    detail = client.get(f"/api/integrations/batches/{res['batch_id']}", headers=h).json()
    assert detail["transactions_total"] == 1
    assert detail["transactions"][0]["reference"].startswith("NEFTN")
    rows = client.get(f"/api/transactions?import_batch_id={res['batch_id']}",
                      headers=h).json()
    assert (rows.get("total") or len(rows.get("items") or rows.get("transactions") or [])) == 1

    # 4. same file again: nothing new, payables unchanged
    again = _import(client, h, _csv(item)).json()
    assert again["rows_imported"] == 0
    assert client.get("/api/overview" + Q1, headers=h).json()["headline"]["payables"]["paise"] \
        == pay_after

    # 5. yesterday is still yesterday
    old = client.get("/api/suppliers" + Q0, headers=h).json()
    assert any(i["invoice_no"] == item["invoice_no"] for i in old["msmed"]["items"])
