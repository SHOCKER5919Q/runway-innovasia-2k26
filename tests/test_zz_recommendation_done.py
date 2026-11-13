"""Marking a cash recommendation done records the money; Undo removes it."""
from conftest import TODAY

Q = f"?as_of={TODAY.isoformat()}"


def _head(client, h):
    return client.get("/api/overview" + Q, headers=h).json()["headline"]


def test_collect_overdue_done_moves_cash_and_undo_restores(client, owner_auth):
    h = owner_auth
    before = _head(client, h)
    r = client.post("/api/recommendations/collect_overdue/status" + Q, headers=h,
                    json={"status": "done"})
    assert r.status_code == 200, r.text
    led = r.json()["ledger"]
    assert led["recorded"] and led["total_paise"] > 0
    after = _head(client, h)
    assert after["cash_in_hand"]["paise"] - before["cash_in_hand"]["paise"] == led["total_paise"]
    assert before["receivables"]["paise"] - after["receivables"]["paise"] == led["total_paise"]
    status = next(x["status"] for x in client.get("/api/recommendations" + Q, headers=h)
                  .json()["recommendations"] if x["code"] == "collect_overdue")
    assert status == "done"
    client.post("/api/recommendations/collect_overdue/status" + Q, headers=h,
                json={"status": "open"})
    again = _head(client, h)
    assert again["cash_in_hand"]["paise"] == before["cash_in_hand"]["paise"]
    assert again["receivables"]["paise"] == before["receivables"]["paise"]
