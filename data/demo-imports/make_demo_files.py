"""Write the live-demo import files. Deterministic: same output every run.

    backend/.venv/bin/python data/demo-imports/make_demo_files.py

Every party and invoice number below exists in the seeded demo workspace
(Sri Lakshmi Industrial Supplies, scenario B, as of 2026-11-07), so the
matcher has something real to match. Amounts are the invoices' exact open
balances. Each file is one later day, so they are imported in order and
the as-of date moves forward with them - see docs/DEMO_IMPORTS.md.

These are DEMO files, written for this synthetic workspace. They are not
real bank exports; the real-data example is data/real/uci_online_retail_ii.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def w(name: str, text: str) -> None:
    (HERE / name).write_text(text, encoding="utf-8")


def bank_day1() -> None:
    # HDFC-style export: dd/mm/yyyy, "Withdrawal Amt." / "Deposit Amt.".
    # Row 3 repeats row 2 exactly, to show the duplicate detector.
    w("01-hdfc-statement-2026-11-08.csv",
      "Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"
      "08/11/2026,NEFT DR-XYZ FOODS PVT LTD-PUR-5352,NEFTN26110801,08/11/26,352791.11,,388463.62\n"
      "08/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1738,NEFTN26110802,08/11/26,,27584.69,416048.31\n"
      "08/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1738,NEFTN26110802,08/11/26,,27584.69,416048.31\n"
      "08/11/2026,SMS ALERT CHARGES OCT-26,,08/11/26,59.00,,415989.31\n")


def bank_day2_xlsx() -> None:
    # The same bank, downloaded as Excel, with currency-tagged headers.
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Statement"
    ws.append(["Statement of account - Current A/c XXXX4417"])
    ws.append([])
    ws.append(["Txn Date", "Description", "Ref No", "Withdrawal (INR)", "Deposit (INR)"])
    rows = [
        ("2026-11-09", "NEFT DR-CHARMINAR LOGISTICS-PUR-5364", "NEFTN26110901", 77537.74, None),
        ("2026-11-09", "NEFT CR-ABC DISTRIBUTORS-INV-1778", "NEFTN26110902", None, 79421.51),
        ("2026-11-09", "TSSPDCL ELECTRICITY BILL OCT-26", "BBPS2611099", 18450.00, None),
    ]
    from datetime import date
    for d, n, r, wd, dp in rows:
        ws.append([date.fromisoformat(d), n, r, wd, dp])
    wb.properties.creator = "RUNWAY demo"
    from datetime import datetime
    wb.properties.created = wb.properties.modified = datetime(2026, 11, 9)
    wb.save(HERE / "02-hdfc-statement-2026-11-09.xlsx")


def razorpay_day3() -> None:
    # Gateway settlement: gross, fee and net, keyed to the invoice paid.
    w("03-razorpay-settlement-2026-11-10.csv",
      "Settlement Date,Payment Id,Gross Amount,Fee,Net Amount,Order Id\n"
      "2026-11-10,pay_RW26111001,37332.62,317.33,37015.29,INV-1793\n"
      "2026-11-10,pay_RW26111002,73737.85,626.77,73111.08,INV-1803\n")


def gst_day4() -> None:
    # Two new sales invoices to existing customers: receivables go up.
    w("04-gstr1-sales-register-2026-11-11.csv",
      "Invoice No,Invoice Date,Customer Name,Taxable Value,IGST,Invoice Value\n"
      "INV-1933,11/11/2026,ABC Distributors,180000.00,32400.00,212400.00\n"
      "INV-1934,11/11/2026,Nandi Retail Mart,95000.00,17100.00,112100.00\n")


def tally_day5() -> None:
    w("05-tally-daybook-2026-11-12.xml",
      '<?xml version="1.0" encoding="UTF-8"?>\n'
      "<ENVELOPE><BODY><IMPORTDATA><REQUESTDATA>\n"
      '<TALLYMESSAGE><VOUCHER VCHTYPE="Receipt">'
      "<DATE>20261112</DATE><VOUCHERNUMBER>RCT-311</VOUCHERNUMBER>"
      "<PARTYLEDGERNAME>ABC Distributors</PARTYLEDGERNAME>"
      "<NARRATION>Against INV-1805</NARRATION><AMOUNT>82420.45</AMOUNT>"
      "</VOUCHER></TALLYMESSAGE>\n"
      '<TALLYMESSAGE><VOUCHER VCHTYPE="Payment">'
      "<DATE>20261112</DATE><VOUCHERNUMBER>PMT-118</VOUCHERNUMBER>"
      "<PARTYLEDGERNAME>Godavari Packaging</PARTYLEDGERNAME>"
      "<NARRATION>Against PUR-5337</NARRATION><AMOUNT>-201270.28</AMOUNT>"
      "</VOUCHER></TALLYMESSAGE>\n"
      "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>\n")


def pdf_invoice() -> None:
    """A one-page text-layer PDF, written by hand (no PDF library needed)."""
    lines = [
        "TAX INVOICE",
        "Sri Lakshmi Industrial Supplies, Hyderabad",
        "GSTIN: 36AAACS1234F1Z5",
        "Invoice No: INV-1935",
        "Invoice Date: 12/11/2026",
        "Bill to: Sri Balaji Agencies",
        "Taxable Value: 140,000.00",
        "IGST 18%: 25,200.00",
        "Grand Total: 165,200.00",
        "Payment terms: 45 days",
    ]
    y, body = 780, []
    for ln in lines:
        safe = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        body.append(f"BT /F1 12 Tf 60 {y} Td ({safe}) Tj ET")
        y -= 22
    stream = "\n".join(body).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    (HERE / "06-sales-invoice-INV-1935.pdf").write_bytes(bytes(out))


def bad_file() -> None:
    # No date column and no amount columns: must be refused with a clear reason.
    w("07-broken-statement-no-dates.csv",
      "Particular,Value,Remarks\n"
      "Something,100,Missing the columns a statement needs\n")


def gst_json_alt() -> None:
    # The GSTR-1 JSON shape from the GST portal, as a second GST format.
    w("08-gstr1-b2b-portal-format.json", json.dumps({"b2b": [{
        "ctin": "36AABCU9603R1ZX",
        "inv": [{"inum": "INV-1936", "idt": "13-11-2026", "val": 59000.00,
                 "txval": 50000.00, "iamt": 9000.00}]}]}, indent=1) + "\n")


if __name__ == "__main__":
    for f in (bank_day1, bank_day2_xlsx, razorpay_day3, gst_day4, tally_day5,
              pdf_invoice, bad_file, gst_json_alt):
        f()
    for p in sorted(HERE.iterdir()):
        if p.suffix != ".py":
            print(f"{p.name:44} {p.stat().st_size:>6} bytes")
