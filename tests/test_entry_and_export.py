"""Manual entry, exports and shareable briefings.

The entry endpoints are the only place in RUNWAY where a human can write
straight into the ledger, so the tests concentrate on what could go wrong
there: creating money out of nothing, double-counting a row, letting a typed
row outrank a bank record, or letting someone delete an imported one.

The export tests are about honesty of *rendering*: a CSV must keep paise
integral, must say which state each figure came from, and must not silently
drop rows that did not fit.
"""
from __future__ import annotations

import csv
import io
from datetime import date

import pytest

TODAY = date(2026, 11, 7)
AS = f"?as_of={TODAY.isoformat()}"


def _rows(resp):
    assert resp.status_code == 200, resp.text[:400]
    # utf-8-sig: the exports carry a BOM so Excel reads ₹ correctly, and the
    # reader has to drop it before the header can be compared by name.
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


# ───────────────────────── manual transactions ─────────────────────────

def test_a_typed_transaction_runs_the_same_pipeline_as_an_import(client, owner_auth):
    r = client.post("/api/transactions", headers=owner_auth, json={
        "value_date": "2026-11-03", "direction": "debit", "amount_rupees": 12500.50,
        "narration": "Paid to Godavari Packaging for cartons",
        "counterparty_name": "Godavari Packaging"})
    assert r.status_code == 201, r.text[:400]
    d = r.json()
    assert d["amount"]["paise"] == 1_250_050, "rupees must land as whole paise"
    assert d["source_system"] == "manual"
    # Classified and counterparty-resolved like any imported row.
    assert d["category"], "a typed row must still be classified"
    assert d["counterparty"], "the narration names a known supplier"
    assert d["pipeline"]["classification"]
    # A hand-typed row is an owner statement until it is matched to something.
    assert d["evidence"] in ("owner_estimate", "verified_actual")


def test_a_manual_transaction_never_takes_the_future(client, owner_auth):
    r = client.post("/api/transactions", headers=owner_auth, json={
        "value_date": "2027-01-01", "direction": "debit", "amount_rupees": 100,
        "narration": "something that has not happened yet"})
    assert r.status_code == 400


def test_an_identical_reference_is_rejected_not_merged(client, owner_auth):
    body = {"value_date": "2026-11-02", "direction": "credit", "amount_rupees": 4_000,
            "narration": "NEFT from test customer", "reference_no": "NEFT-TEST-1",
            "counterparty_name": "Test Party Alpha"}
    first = client.post("/api/transactions", headers=owner_auth, json=body)
    assert first.status_code == 201, first.text[:400]
    again = client.post("/api/transactions", headers=owner_auth, json=body)
    # Hard duplicate: the same bank reference cannot be posted twice.
    assert again.status_code == 409
    assert "existing_transaction_id" in again.json()["detail"]
    client.delete(f"/api/transactions/{first.json()['id']}", headers=owner_auth)


def test_a_similar_row_without_a_reference_is_flagged_not_dropped(client, owner_auth):
    body = {"value_date": "2026-11-02", "direction": "credit", "amount_rupees": 7_777,
            "narration": "Cash received at the counter",
            "counterparty_name": "Test Party Beta"}
    first = client.post("/api/transactions", headers=owner_auth, json=body)
    assert first.status_code == 201
    again = client.post("/api/transactions", headers=owner_auth, json=body)
    # Without a bank reference the engine refuses to decide: it keeps the row
    # and flags it, because a business genuinely can be paid twice.
    assert again.status_code == 201
    assert again.json()["duplicate_of"] == first.json()["id"]
    for txn in (first, again):
        client.delete(f"/api/transactions/{txn.json()['id']}", headers=owner_auth)


def test_a_payment_that_settles_an_invoice_is_promoted_to_verified(client, owner_auth):
    """A typed row matched against a real invoice is no longer a bare claim."""
    inv = client.post("/api/invoices", headers=owner_auth, json={
        "kind": "sales", "invoice_no": "INV-TEST-9001",
        "counterparty_name": "Test Party Gamma", "issue_date": "2026-10-05",
        "credit_days": 15, "amount_rupees": 50_000}).json()
    assert inv["outstanding"]["paise"] == 5_000_000

    pay = client.post("/api/transactions", headers=owner_auth, json={
        "value_date": "2026-10-20", "direction": "credit", "amount_rupees": 50_000,
        "narration": "NEFT towards INV-TEST-9001",
        "counterparty_name": "Test Party Gamma"})
    assert pay.status_code == 201, pay.text[:400]
    assert pay.json()["recon_status"] == "matched"
    assert pay.json()["evidence"] == "verified_actual"

    got = client.get(f"/api/invoices/{inv['id']}{AS}", headers=owner_auth).json()
    assert got["status"] == "paid"
    assert got["outstanding"]["paise"] == 0

    # Deleting the payment must un-pay the invoice, or the ledger would keep a
    # settlement for money that no longer exists.
    client.delete(f"/api/transactions/{pay.json()['id']}", headers=owner_auth)
    got = client.get(f"/api/invoices/{inv['id']}{AS}", headers=owner_auth).json()
    assert got["settled"]["paise"] == 0
    assert got["status"] in ("open", "overdue")
    client.delete(f"/api/invoices/{inv['id']}", headers=owner_auth)


def test_deleting_a_manual_row_releases_what_it_settled(client, owner_auth):
    inv = client.post("/api/invoices", headers=owner_auth, json={
        "kind": "sales", "invoice_no": "INV-TEST-9002",
        "counterparty_name": "Test Party Delta", "issue_date": "2026-10-01",
        "credit_days": 10, "amount_rupees": 20_000}).json()
    pay = client.post("/api/transactions", headers=owner_auth, json={
        "value_date": "2026-10-11", "direction": "credit", "amount_rupees": 20_000,
        "narration": "NEFT INV-TEST-9002", "counterparty_name": "Test Party Delta"}).json()
    assert pay["recon_status"] == "matched"
    d = client.delete(f"/api/transactions/{pay['id']}", headers=owner_auth).json()
    assert d["released_allocations"], "the settlement must be undone with the row"
    assert d["released_allocations"][0]["invoice_no"] == "INV-TEST-9002"
    client.delete(f"/api/invoices/{inv['id']}", headers=owner_auth)


def test_an_imported_transaction_cannot_be_deleted(client, owner_auth):
    """Imported rows are somebody else's record. They get corrected, not erased."""
    listed = client.get("/api/transactions?page_size=50", headers=owner_auth).json()
    imported = next(t for t in listed["items"] if t["source_system"] != "manual")
    r = client.delete(f"/api/transactions/{imported['id']}", headers=owner_auth)
    assert r.status_code == 409
    assert client.get(f"/api/transactions/{imported['id']}",
                      headers=owner_auth).status_code == 200


def test_the_accountant_cannot_write_to_the_ledger(client, ca_auth):
    tok = ca_auth["token"]
    headers = {"Authorization": f"Bearer {tok}",
               "X-Business-Id": ca_auth["active_business_id"]}
    r = client.post("/api/transactions", headers=headers, json={
        "value_date": "2026-11-03", "direction": "debit", "amount_rupees": 500,
        "narration": "unauthorised"})
    assert r.status_code == 403


def test_a_transaction_cannot_be_written_without_a_token(client, business_id):
    r = client.post("/api/transactions", headers={"X-Business-Id": business_id}, json={
        "value_date": "2026-11-03", "direction": "debit", "amount_rupees": 500,
        "narration": "anonymous"})
    assert r.status_code == 401


# ─────────────────────────── manual invoices ───────────────────────────

def test_an_invoice_splits_tax_and_total_correctly(client, owner_auth):
    r = client.post("/api/invoices", headers=owner_auth, json={
        "kind": "purchase", "invoice_no": "PUR-TEST-7001",
        "counterparty_name": "Test Supplier Epsilon", "issue_date": "2026-10-12",
        "due_date": "2026-11-11", "amount_rupees": 118_000, "gst_rate": 0.18})
    assert r.status_code == 201, r.text[:400]
    d = r.json()
    assert d["total"]["paise"] == 11_800_000
    assert d["taxable"]["paise"] + d["tax"]["paise"] == d["total"]["paise"]
    assert d["tax"]["paise"] == pytest.approx(1_800_000, abs=200)
    assert d["due_date"] == "2026-11-11"
    assert d["kind"] == "purchase"
    client.delete(f"/api/invoices/{d['id']}", headers=owner_auth)


def test_an_invoice_number_cannot_be_reused_in_the_same_kind(client, owner_auth):
    body = {"kind": "sales", "invoice_no": "INV-TEST-DUPE",
            "counterparty_name": "Test Party Zeta", "issue_date": "2026-10-01",
            "amount_rupees": 1_000}
    first = client.post("/api/invoices", headers=owner_auth, json=body)
    assert first.status_code == 201
    again = client.post("/api/invoices", headers=owner_auth, json=body)
    assert again.status_code == 409
    client.delete(f"/api/invoices/{first.json()['id']}", headers=owner_auth)


def test_a_new_invoice_is_matched_against_payments_already_on_the_books(client, owner_auth):
    """The owner often raises last month's bill after the money has arrived.

    Forward-only matching would leave that invoice open forever next to the
    payment that plainly belongs to it.
    """
    pay = client.post("/api/transactions", headers=owner_auth, json={
        "value_date": "2026-10-25", "direction": "credit", "amount_rupees": 30_000,
        "narration": "NEFT towards INV-TEST-9003",
        "counterparty_name": "Test Party Eta"}).json()
    assert pay["recon_status"] in ("unreconciled", "needs_review"), (
        "there is nothing to match yet")

    inv = client.post("/api/invoices", headers=owner_auth, json={
        "kind": "sales", "invoice_no": "INV-TEST-9003",
        "counterparty_name": "Test Party Eta", "issue_date": "2026-10-10",
        "credit_days": 15, "amount_rupees": 30_000}).json()
    assert inv["pipeline"]["auto_matched_payments"], (
        "the payment already on the books must settle this invoice")
    got = client.get(f"/api/invoices/{inv['id']}{AS}", headers=owner_auth).json()
    assert got["status"] == "paid"
    client.delete(f"/api/invoices/{inv['id']}", headers=owner_auth)
    client.delete(f"/api/transactions/{pay['id']}", headers=owner_auth)


def test_a_counterparty_is_created_once_and_matched_after_that(client, owner_auth):
    body = {"name": "Test Party Theta", "party_type": "supplier", "credit_days": 45}
    first = client.post("/api/counterparties", headers=owner_auth, json=body)
    assert first.status_code == 201
    assert first.json()["note"].startswith("created")
    again = client.post("/api/counterparties", headers=owner_auth, json=body)
    assert again.status_code == 409, "a second party with the same name is a typo"


# ───────────────────────────── exports ─────────────────────────────────

@pytest.mark.parametrize("path", ["/api/exports/transactions.csv",
                                  "/api/exports/receivables.csv",
                                  "/api/exports/payables.csv",
                                  "/api/exports/passport.csv"])
def test_exports_are_csv_and_downloadable(client, owner_auth, path):
    r = client.get(path + AS, headers=owner_auth)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment;" in r.headers["content-disposition"]
    rows = _rows(r)
    assert len(rows) > 1, "an export with only a header is a bug"
    assert len({len(x) for x in rows}) == 1, "every row must have the same width"


def test_transaction_export_keeps_paise_integral(client, owner_auth):
    rows = _rows(client.get("/api/exports/transactions.csv", headers=owner_auth))
    head, body = rows[0], rows[1:]
    i_paise, i_rupees = head.index("amount_paise"), head.index("amount_rupees")
    for r in body:
        assert str(int(r[i_paise])) == r[i_paise], "paise must be a whole number"
        assert int(r[i_paise]) > 0
        assert abs(float(r[i_rupees]) * 100 - int(r[i_paise])) < 1.0


def test_receivables_export_labels_predictions_as_predictions(client, owner_auth):
    rows = _rows(client.get("/api/exports/receivables.csv" + AS, headers=owner_auth))
    head, body = rows[0], rows[1:]
    assert "predicted_state" in head
    i_state, i_pred = head.index("predicted_state"), head.index("predicted_pay_date")
    assert body, "the collection list must not be empty"
    for r in body:
        assert r[i_state] == "predicted", (
            "a forwarded CSV must say which figures are model output")


def test_passport_export_carries_its_own_basis_and_evidence(client, owner_auth):
    rows = _rows(client.get("/api/exports/passport.csv" + AS, headers=owner_auth))
    head, body = rows[0], rows[1:]
    assert head[:4] == ["section_key", "section", "field", "value"]
    assert "basis" in head and "evidence" in head
    assert body
    keys = {r[0] for r in body}
    assert "liquidity" in keys and "data_coverage" in keys
    # No row may ship a number with no stated basis attached to it.
    assert all(r[4] for r in body), "every disclosed figure carries its basis"


def test_exports_require_a_token(client, business_id):
    for p in ("/api/exports/transactions.csv", "/api/exports/passport.csv"):
        assert client.get(p).status_code == 401


# ──────────────────────────── briefings ────────────────────────────────

def test_the_whatsapp_briefing_is_plain_text_and_fits_a_phone(client, owner_auth):
    d = client.get("/api/briefing/whatsapp" + AS, headers=owner_auth).json()
    assert d["channel"] == "whatsapp"
    assert "\n" in d["text"]
    assert "<" not in d["text"], "no markup survives into a chat message"
    assert d["char_count"] == len(d["text"])
    assert d["char_count"] < 2000, "a briefing nobody scrolls to is useless"
    assert d["share_url"].startswith("https://wa.me/")


def test_the_briefing_says_which_figures_are_predictions(client, owner_auth):
    """A forwarded note is read by people who have never opened the app."""
    d = client.get("/api/briefing/whatsapp" + AS, headers=owner_auth).json()
    text = d["text"].lower()
    assert "predicted" in text or "prediction" in text
    assert d["disclaimer"]


def test_the_email_briefing_has_a_subject_and_a_mailto(client, owner_auth):
    d = client.get("/api/briefing/email" + AS, headers=owner_auth).json()
    assert d["subject"]
    assert len(d["subject"]) < 120
    assert d["mailto_url"].startswith("mailto:")


def test_a_collection_reminder_uses_the_customers_own_numbers(client, owner_auth):
    inv = client.get("/api/receivables" + AS, headers=owner_auth).json()
    item = next(c for c in inv["collection_list"] if c["days_past_due"] > 0)
    d = client.get(f"/api/receivables/{item['invoice_id']}/reminder{AS}",
                   headers=owner_auth).json()
    assert d["invoice_no"] == item["invoice_no"]
    assert d["outstanding"]["paise"] == item["outstanding_paise"]
    assert d["text"]
    assert str(d["days_past_due"]) in d["text"]
    assert d["note"], "the owner must be told RUNWAY did not send this"


@pytest.mark.parametrize("tone", ["polite", "firm", "final"])
def test_reminder_tone_changes_the_wording_not_the_facts(client, owner_auth, tone):
    inv = client.get("/api/receivables" + AS, headers=owner_auth).json()
    item = next(c for c in inv["collection_list"] if c["days_past_due"] > 0)
    d = client.get(f"/api/receivables/{item['invoice_id']}/reminder{AS}&tone={tone}",
                   headers=owner_auth).json()
    assert d["tone"] == tone
    assert d["outstanding"]["paise"] == item["outstanding_paise"]
    assert d["text"]


def test_an_unknown_tone_is_rejected(client, owner_auth):
    inv = client.get("/api/receivables" + AS, headers=owner_auth).json()
    item = inv["collection_list"][0]
    r = client.get(f"/api/receivables/{item['invoice_id']}/reminder{AS}&tone=angry",
                   headers=owner_auth)
    assert r.status_code == 422


def test_a_reminder_cannot_be_composed_for_another_businesses_invoice(
        client, owner_auth, second_business_id):
    """Otherwise the endpoint would be a way to enumerate other ledgers."""
    r = client.get(f"/api/receivables/does-not-exist/reminder{AS}", headers=owner_auth)
    assert r.status_code == 404
    headers = {**owner_auth, "X-Business-Id": second_business_id}
    assert client.get("/api/receivables" + AS, headers=headers).status_code == 403


def test_reminders_csv_lists_every_overdue_invoice(client, owner_auth):
    r = client.get("/api/receivables/reminders.csv" + AS, headers=owner_auth)
    rows = _rows(r)
    head, body = rows[0], rows[1:]
    assert head[0] == "invoice_no"
    all_overdue = [c for c in
                   client.get("/api/receivables" + AS,
                              headers=owner_auth).json()["collection_list"]
                   if c["days_past_due"] >= 1]
    assert len(body) == len(all_overdue)
    for row in body:
        assert row[6] == "firm"
        assert row[7], "every row carries a ready-to-send message"
