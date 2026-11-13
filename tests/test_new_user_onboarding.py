"""End-to-end tests for a naive new user signing up, entering financial data,
and running every feature against their own ledger."""
from __future__ import annotations

from datetime import date, timedelta


def test_new_user_signup_and_full_feature_flow(client):
    today = date.today()

    # 1. Register a brand-new user + business with opening cash and safety floor
    reg = client.post("/api/auth/register", json={
        "email": "naive-owner@precision.in",
        "password": "securepassword123",
        "full_name": "Ramesh Kumar",
        "business_name": "Sri Sai Precision Works",
        "industry": "manufacturing",
        "city": "Hyderabad",
        "opening_balance_paise": 500_000_00,   # Rs 5,00,000
        "overdraft_limit_paise": 200_000_00,   # Rs 2,00,000
        "safety_buffer_paise": 150_000_00,     # Rs 1,50,000
        "account_name": "HDFC Current",
        "bank_name": "HDFC Bank",
    })
    assert reg.status_code == 201, reg.text
    session = reg.json()
    biz_id = session["active_business_id"]
    assert biz_id
    assert session["businesses"][0]["is_demo"] is False
    hdr = {"Authorization": f"Bearer {session['token']}", "X-Business-Id": biz_id}

    # 2. Verify a default primary bank account was created automatically
    accs = client.get("/api/integrations/accounts", headers=hdr).json()["accounts"]
    assert len(accs) == 1
    acc_id = accs[0]["id"]
    assert accs[0]["name"] == "HDFC Current"

    # 3. Update account & add a second cash account
    upd = client.patch(f"/api/accounts/{acc_id}", headers=hdr,
                       json={"restricted_paise": 50_000_00})
    assert upd.status_code == 200
    acc2 = client.post("/api/accounts", headers=hdr, json={
        "name": "Petty Cash", "kind": "cash", "opening_balance_paise": 25_000_00,
    })
    assert acc2.status_code == 201

    # 4. Add manual sales invoice & micro-MSME supplier bill (+ duplicate rejection check)
    s_inv = client.post("/api/invoices", headers=hdr, json={
        "kind": "sales",
        "counterparty_name": "Telangana Gears Ltd",
        "invoice_no": "SS-INV-01",
        "issue_date": (today - timedelta(days=40)).isoformat(),
        "due_date": (today - timedelta(days=10)).isoformat(),
        "total_paise": 300_000_00,
    })
    assert s_inv.status_code == 201, s_inv.text
    assert s_inv.json()["status"] == "overdue"

    dup_inv = client.post("/api/invoices", headers=hdr, json={
        "kind": "sales",
        "counterparty_name": "Telangana Gears Ltd",
        "invoice_no": "SS-INV-01",
        "issue_date": today.isoformat(),
        "total_paise": 300_000_00,
    })
    assert dup_inv.status_code == 409

    p_bill = client.post("/api/invoices", headers=hdr, json={
        "kind": "purchase",
        "counterparty_name": "Anand Fasteners Micro",
        "invoice_no": "AF-BILL-01",
        "issue_date": (today - timedelta(days=30)).isoformat(),
        "due_date": (today + timedelta(days=15)).isoformat(),
        "total_paise": 120_000_00,
        "msme_class": "micro",
    })
    assert p_bill.status_code == 201, p_bill.text

    # 5. Bulk import invoices_csv (including settled history + open bills) & check duplicate handling
    csv_bytes = (
        "type,invoice_no,party,issue_date,due_date,total,tax,paid,settled_date,msme_class\n"
        f"sales,SS-INV-02,Apex Hydraulics,{(today - timedelta(days=60)).isoformat()},{(today - timedelta(days=30)).isoformat()},200000,30508,200000,{(today - timedelta(days=20)).isoformat()},\n"
        f"sales,SS-INV-03,Apex Hydraulics,{(today - timedelta(days=5)).isoformat()},{(today + timedelta(days=25)).isoformat()},250000,38136,0,,\n"
        f"purchase,KP-BILL-02,Kaveri Polymers,{(today - timedelta(days=10)).isoformat()},{(today + timedelta(days=20)).isoformat()},90000,13729,0,,small\n"
    ).encode()
    imp = client.post(
        "/api/integrations/import",
        headers=hdr,
        data={"adapter": "invoices_csv", "account_id": acc_id, "dry_run": "false"},
        files={"file": ("invoices.csv", csv_bytes, "text/csv")},
    )
    assert imp.status_code == 200, imp.text
    assert imp.json()["rows_imported"] == 3

    # Re-importing the exact same CSV rejects duplicates cleanly instead of 500
    reimp = client.post(
        "/api/integrations/import",
        headers=hdr,
        data={"adapter": "invoices_csv", "account_id": acc_id, "dry_run": "false"},
        files={"file": ("invoices.csv", csv_bytes, "text/csv")},
    )
    assert reimp.status_code == 200, reimp.text
    assert reimp.json()["duplicates_rejected"] == 3
    assert reimp.json()["rows_imported"] == 0

    # 6. Add recurring monthly obligation & loan
    ob = client.post("/api/obligations", headers=hdr, json={
        "kind": "payroll",
        "label": "Workshop Staff Payroll",
        "due_date": (today + timedelta(days=12)).isoformat(),
        "amount_paise": 140_000_00,
        "is_recurring": True,
        "reserve_cash": True,
    })
    assert ob.status_code == 201, ob.text

    ln = client.post("/api/loans", headers=hdr, json={
        "lender": "SIDBI Machinery Loan",
        "principal_paise": 600_000_00,
        "outstanding_paise": 450_000_00,
        "annual_rate": 0.11,
        "emi_paise": 22_000_00,
        "emi_day": 5,
    })
    assert ln.status_code == 201, ln.text

    # 7. Record a manual partial customer receipt matching SS-INV-01
    txn = client.post("/api/transactions", headers=hdr, json={
        "account_id": acc_id,
        "value_date": today.isoformat(),
        "amount_paise": 100_000_00,
        "direction": "credit",
        "narration": "NEFT CR Telangana Gears Ltd SS-INV-01",
        "counterparty_name": "Telangana Gears Ltd",
        "reference_no": "UTR123456",
    })
    assert txn.status_code == 201, txn.text

    # 8. Verify ALL features compute from this new user's real data
    ov = client.get("/api/overview", headers=hdr)
    assert ov.status_code == 200
    ovj = ov.json()
    assert ovj["business"]["is_demo"] is False
    assert ovj["business"]["name"] == "Sri Sai Precision Works"
    # Opening 5L + 25k + 1L receipt = 6.25L cash in hand
    assert ovj["headline"]["cash_in_hand"]["paise"] == 625_000_00
    # Open receivables: 2L remaining on SS-INV-01 + 2.5L on SS-INV-03 = 4.5L
    assert ovj["headline"]["receivables"]["paise"] == 450_000_00
    # Open payables: 1.2L + 90k = 2.1L
    assert ovj["headline"]["payables"]["paise"] == 210_000_00
    assert ovj["forecast"] is not None and len(ovj["forecast"]["p50"]) >= 13

    for ep in [
        "/api/briefing",
        "/api/states/actual",
        "/api/states/predicted",
        "/api/states/history",
        "/api/states/reconcile",
        "/api/forecast",
        "/api/risk",
        "/api/health",
        "/api/recommendations",
        "/api/twin/state",
        "/api/twin/graph",
        "/api/twin/timeline",
        "/api/receivables",
        "/api/payables",
        "/api/customers",
        "/api/suppliers",
        "/api/compliance",
        "/api/transactions",
        "/api/invoices?kind=sales",
        "/api/accounts",
    ]:
        r = client.get(ep, headers=hdr)
        assert r.status_code == 200, f"{ep}: {r.text[:200]}"

    # Payables shows MSME 43B(h) supplier exposure
    pay = client.get("/api/payables", headers=hdr).json()
    assert pay["msmed"]["covered_outstanding_paise"] == 210_000_00

    # Scenario Lab quick-run works on this user's own baseline
    qr = client.post("/api/scenarios/quick-run", headers=hdr, json={
        "kind": "new_order",
        "parameters": {"order_value_paise": 300_000_00, "margin_pct": 0.2},
        "paths": 600,
    })
    assert qr.status_code == 200, qr.text
    assert qr.json()["baseline_series"]["runway_weeks_p50"] is not None
    assert qr.json()["scenario_series"]["runway_weeks_p50"] is not None

    # Cash Health Passport marks data as supplied by the business (not synthetic demo)
    psp = client.get("/api/reports/passport", headers=hdr)
    assert psp.status_code == 200
    decls = " ".join(psp.json()["declarations"]).lower()
    assert "supplied by the business" in decls
    assert "synthetic" not in decls

    # AI Copilot answers grounded in the user's ledger
    cop = client.post("/api/copilot/ask", headers=hdr, json={
        "question": "What is my available cash and who owes me money?"
    })
    assert cop.status_code == 200, cop.text
    assert cop.json()["answer"]


def _register_clean_business(client, email: str, name: str):
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "securepassword123",
        "full_name": "Owner",
        "business_name": name,
        "opening_balance_paise": 200_000_00,
    })
    assert reg.status_code == 201, reg.text
    s = reg.json()
    hdr = {"Authorization": f"Bearer {s['token']}", "X-Business-Id": s["active_business_id"]}
    acc_id = client.get("/api/integrations/accounts", headers=hdr).json()["accounts"][0]["id"]
    return hdr, acc_id


def test_customer_invoices_and_installment_payments_csv_import_both_orders(client):
    """Exact schemas from business_customer_invoices_multiple_dues.csv &
    business_customer_payments_installments.csv import cleanly in either order
    without double-counting Amount_Paid_INR."""
    invoices_csv = (
        "Invoice_ID,Customer_ID,Customer_Name,Invoice_Date,Due_Date,Purpose,"
        "Invoice_Amount_INR,Amount_Paid_INR,Outstanding_INR,Status_As_Of_2026_11_13,Days_Overdue\n"
        "INV-00001,CUST-0001,BluePeak Retail,2026-02-04,2026-04-05,Mobile app milestone,99957.94,99957.94,0.0,Paid,0\n"
        "INV-00002,CUST-0001,BluePeak Retail,2026-03-11,2026-04-25,Digital marketing,50903.98,26231.7,24672.28,Partially Paid,202\n"
        "INV-00003,CUST-0001,BluePeak Retail - Branch 2,2026-08-24,2026-09-08,Product supply order,91921.2,0.0,91921.2,Overdue,66\n"
        "INV-00006,CUST-0002,Nexa Foods,2026-03-18,2026-05-02,Monthly subscription,5883.02,5883.02,0.0,Paid,0\n"
    ).encode()
    payments_csv = (
        "Payment_ID,Invoice_ID,Customer_ID,Customer_Name,Payment_Date,Payment_Amount_INR,Payment_Mode,Reference\n"
        "PAY-00001,INV-00001,CUST-0001,BluePeak Retail,2026-02-18,99957.94,UPI,UTR-DEMO-0000001\n"
        "PAY-00002,INV-00002,CUST-0001,BluePeak Retail,2026-04-11,26231.7,RTGS,UTR-DEMO-0000002\n"
        "PAY-00003,INV-00006,CUST-0002,Nexa Foods,2026-05-23,1507.47,Bank Transfer,UTR-DEMO-0000003\n"
        "PAY-00004,INV-00006,CUST-0002,Nexa Foods,2026-04-02,4375.55,Bank Transfer,UTR-DEMO-0000004\n"
    ).encode()

    # Order A: Invoices first, then Payments
    hdr_a, acc_a = _register_clean_business(client, "csv-order-a@example.in", "Order A Works")
    r1 = client.post(
        "/api/integrations/import",
        headers=hdr_a,
        data={"adapter": "invoices_csv", "account_id": acc_a, "dry_run": "false"},
        files={"file": ("business_customer_invoices_multiple_dues.csv", invoices_csv, "text/csv")},
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["rows_imported"] == 4
    assert r1.json()["rows_rejected"] == 0

    r2 = client.post(
        "/api/integrations/import",
        headers=hdr_a,
        data={"adapter": "bank_csv", "account_id": acc_a, "dry_run": "false"},
        files={"file": ("business_customer_payments_installments.csv", payments_csv, "text/csv")},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["rows_imported"] == 4
    assert r2.json()["auto_matched"] == 4

    invs_a = {i["invoice_no"]: i for i in client.get("/api/invoices?kind=sales", headers=hdr_a).json()["items"]}
    assert invs_a["INV-00001"]["status"] == "paid"
    assert invs_a["INV-00002"]["outstanding"]["paise"] == 2_467_228
    assert invs_a["INV-00002"]["settled"]["paise"] == 2_623_170
    assert invs_a["INV-00003"]["outstanding"]["paise"] == 9_192_120
    assert invs_a["INV-00006"]["status"] == "paid"
    # Branch customer must stay distinct from main branch
    assert invs_a["INV-00003"]["counterparty"] == "BluePeak Retail - Branch 2"

    for ep in ("/api/overview", "/api/states/predicted", "/api/risk", "/api/customers", "/api/receivables"):
        resp = client.get(ep, headers=hdr_a)
        assert resp.status_code == 200, f"{ep}: {resp.text[:200]}"

    # Order B: Payments first, then Invoices (auto-backfill reconciles)
    hdr_b, acc_b = _register_clean_business(client, "csv-order-b@example.in", "Order B Works")
    p1 = client.post(
        "/api/integrations/import",
        headers=hdr_b,
        data={"adapter": "bank_csv", "account_id": acc_b, "dry_run": "false"},
        files={"file": ("business_customer_payments_installments.csv", payments_csv, "text/csv")},
    )
    assert p1.status_code == 200 and p1.json()["rows_imported"] == 4

    p2 = client.post(
        "/api/integrations/import",
        headers=hdr_b,
        data={"adapter": "invoices_csv", "account_id": acc_b, "dry_run": "false"},
        files={"file": ("business_customer_invoices_multiple_dues.csv", invoices_csv, "text/csv")},
    )
    assert p2.status_code == 200 and p2.json()["rows_imported"] == 4
    assert p2.json()["auto_matched"] == 4

    invs_b = {i["invoice_no"]: i for i in client.get("/api/invoices?kind=sales", headers=hdr_b).json()["items"]}
    assert invs_b["INV-00002"]["outstanding"]["paise"] == 2_467_228
    assert invs_b["INV-00002"]["settled"]["paise"] == 2_623_170
    txns_b = client.get("/api/transactions", headers=hdr_b).json()["items"]
    assert all(t["recon_status"] == "matched" for t in txns_b)


def test_wrong_csv_adapter_returns_clear_guidance_and_upi_accepts_payments(client):
    hdr, acc = _register_clean_business(client, "csv-guide@example.in", "Guidance Works")
    invoices_csv = (
        "Invoice_ID,Customer_Name,Invoice_Date,Due_Date,Invoice_Amount_INR,Amount_Paid_INR\n"
        "INV-1,BluePeak Retail,2026-08-01,2026-09-01,50000,0\n"
    ).encode()
    payments_csv = (
        "Payment_ID,Invoice_ID,Customer_Name,Payment_Date,Payment_Amount_INR,Payment_Mode,Reference\n"
        "PAY-1,INV-1,BluePeak Retail,2026-08-10,50000,UPI,UTR-GUIDE-1\n"
    ).encode()

    wrong_inv_on_bank = client.post(
        "/api/integrations/import",
        headers=hdr,
        data={"adapter": "bank_csv", "account_id": acc, "dry_run": "true"},
        files={"file": ("inv.csv", invoices_csv, "text/csv")},
    ).json()
    assert "Invoices & supplier bills" in wrong_inv_on_bank["errors"][0]["error"]

    wrong_pay_on_inv = client.post(
        "/api/integrations/import",
        headers=hdr,
        data={"adapter": "invoices_csv", "account_id": acc, "dry_run": "true"},
        files={"file": ("pay.csv", payments_csv, "text/csv")},
    ).json()
    assert "Bank statement" in wrong_pay_on_inv["errors"][0]["error"]

    upi_preview = client.post(
        "/api/integrations/import",
        headers=hdr,
        data={"adapter": "upi_settlement_csv", "account_id": acc, "dry_run": "true"},
        files={"file": ("pay.csv", payments_csv, "text/csv")},
    )
    assert upi_preview.status_code == 200
    assert upi_preview.json()["rows_seen"] == 1
    assert upi_preview.json()["rows_rejected"] == 0
