"""Import every demo file in order and check what each one changes.

Run it against a server on a COPY of the demo database (it writes imports):

    cp data/runway.db /tmp/demo-check.db
    (cd backend && RUNWAY_DATABASE_URL=sqlite:////tmp/demo-check.db \\
        .venv/bin/uvicorn app.main:app --port 8010) &
    backend/.venv/bin/python data/demo-imports/check_demo_imports.py --api http://127.0.0.1:8010

Prints, for every file: rows read / imported / duplicates / rejected, the
before-and-after figures recorded on the batch, and PASS/FAIL for the
specific thing that file is meant to demonstrate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent

# file, adapter, as-of date, what it should demonstrate
PLAN = [
    ("01-hdfc-statement-2026-11-08.csv", "bank_csv", "2026-11-08"),
    ("02-hdfc-statement-2026-11-09.xlsx", "bank_csv", "2026-11-09"),
    ("03-razorpay-settlement-2026-11-10.csv", "upi_settlement_csv", "2026-11-10"),
    ("04-gstr1-sales-register-2026-11-11.csv", "gst_invoice_json", "2026-11-11"),
    ("05-tally-daybook-2026-11-12.xml", "tally_xml", "2026-11-12"),
    ("06-sales-invoice-INV-1935.pdf", "pdf_invoice", "2026-11-12"),
    ("07-broken-statement-no-dates.csv", "bank_csv", "2026-11-12"),
    ("08-gstr1-b2b-portal-format.json", "gst_invoice_json", "2026-11-13"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8010")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=300)
    s = c.post("/api/auth/login", json={"email": "owner@runway.demo",
                                         "password": "demo1234"}).json()
    biz = next(b["id"] for b in s["businesses"] if b["name"].startswith("Sri Lakshmi"))
    h = {"Authorization": f"Bearer {s['token']}", "X-Business-Id": biz}
    acc = next(x["id"] for x in c.get("/api/integrations/accounts", headers=h).json()["accounts"]
               if x["kind"] == "current")

    def head(as_of):
        o = c.get(f"/api/overview?as_of={as_of}", headers=h).json()["headline"]
        return o

    def msmed_items(as_of):
        return {i["invoice_no"] for i in
                c.get(f"/api/suppliers?as_of={as_of}", headers=h).json()["msmed"]["items"]}

    results, fails = [], 0

    def check(name, ok, detail=""):
        nonlocal fails
        fails += not ok
        results.append((name, ok, detail))

    for fname, adapter, as_of in PLAN:
        data = (HERE / fname).read_bytes()
        files = {"file": (fname, data)}
        form = {"adapter": adapter, "account_id": acc}
        dry = c.post(f"/api/integrations/import?as_of={as_of}", headers=h,
                     data={**form, "dry_run": "true"}, files=files)
        before = head(as_of)
        r = c.post(f"/api/integrations/import?as_of={as_of}", headers=h,
                   data={**form, "dry_run": "false"}, files=files)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(f"\n== {fname}  [{adapter}, as of {as_of}]  HTTP {r.status_code}")
        if r.status_code != 200:
            print("   refused:", body.get("detail", r.text[:200]))
        else:
            print(f"   read {body.get('rows_seen')}  imported {body.get('rows_imported')}  "
                  f"invoices {body.get('invoices_imported', '-')}  "
                  f"duplicates {body.get('duplicates_rejected', body.get('rows_duplicate'))}  "
                  f"rejected {body.get('rows_rejected')}")
            for ch in (body.get("impact") or {}).get("changes", []):
                if ch["change"]:
                    print(f"   {ch['label']:28} {ch['before']!s:>16} -> {ch['after']!s:>16}")
        after = head(as_of)

        if fname.startswith("01"):
            check("01 duplicate row caught", body.get("duplicates_rejected", 0) >= 1)
            check("01 MSMED breach PUR-5352 cleared", "PUR-5352" not in msmed_items(as_of))
            check("01 payables fell by 3,52,791.11",
                  before["payables"]["paise"] - after["payables"]["paise"] == 35279111,
                  f"{before['payables']['paise'] - after['payables']['paise']}")
            check("01 7 Nov view unchanged (PUR-5352 still overdue then)",
                  "PUR-5352" in msmed_items("2026-11-07"))
        if fname.startswith("02"):
            check("02 Excel file read, 3 rows", body.get("rows_imported") == 3,
                  str(body.get("rows_imported")))
        if fname.startswith("03"):
            check("03 gateway settlements imported", (body.get("rows_imported") or 0) == 2,
                  str(body.get("rows_imported")))
        if fname.startswith("04"):
            check("04 receivables up by the two new invoices (3,24,500)",
                  after["receivables"]["paise"] - before["receivables"]["paise"] == 32450000,
                  f"{after['receivables']['paise'] - before['receivables']['paise']}")
        if fname.startswith("05"):
            check("05 Tally vouchers imported", (body.get("rows_imported") or 0) == 2,
                  str(body.get("rows_imported")))
        if fname.startswith("06"):
            check("06 PDF invoice read", r.status_code == 200, str(body)[:160])
        if fname.startswith("07"):
            errs = (dry.json().get("errors") if dry.status_code == 200 else None) or []
            check("07 broken file refused with a reason",
                  r.status_code != 200 or (body.get("rows_imported") == 0 and body.get("errors")),
                  str(body.get("errors") or body.get("detail"))[:160])
        if fname.startswith("08"):
            check("08 GSTR-1 JSON booked as a sale: receivables up 59,000",
                  r.status_code == 200 and
                  after["receivables"]["paise"] - before["receivables"]["paise"] == 5900000,
                  f"{after['receivables']['paise'] - before['receivables']['paise']}")

    hist = c.get("/api/integrations/batches", headers=h).json()["batches"]
    check("history keeps every upload", len(hist) >= 7, f"{len(hist)} batches")
    print("\n" + "\n".join(f"{'PASS' if ok else 'FAIL'}  {n}  {d}" for n, ok, d in results))
    print(f"\n{len(results) - fails}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
