# Live demo: importing files (for the judges)

Sign in as **owner@runway.demo / demo1234**. Go to **Integrations**, pick the
adapter, pick *Current A/c - HDFC Bank*, choose the file, press **Preview**
(nothing is written), then **Import**. Set the as-of date in **Settings** to
the date in the file name before each import (the books move forward a day).

All files are in `data/demo-imports/`. They use the demo workspace's real
customers, suppliers and open invoice numbers. Every result below was
produced by `data/demo-imports/check_demo_imports.py` against a copy of the
database (12/12 checks pass).

| # | File | Adapter | As of | What to show | What changes |
|---|---|---|---|---|---|
| 1 | `01-hdfc-statement-2026-11-08.csv` | Bank statement | 2026-11-08 | Duplicate detector: row 3 repeats row 2 and is rejected. Payment to XYZ Foods for PUR-5352 | Payables −₹3,52,791.11; the **MSMED breach alert clears**; ABC Distributors INV-1738 receipt matched |
| 2 | `02-hdfc-statement-2026-11-09.xlsx` | Bank statement | 2026-11-09 | **Excel** upload with "Withdrawal (INR)" headers | 3 rows; Charminar Logistics PUR-5364 paid (payables −₹77,537.74); receivables −₹79,421.51 |
| 3 | `03-razorpay-settlement-2026-11-10.csv` | UPI / gateway | 2026-11-10 | Gross, fee and net per settlement | Receivables −₹1,11,070.47 (INV-1793, INV-1803) |
| 4 | `04-gstr1-sales-register-2026-11-11.csv` | GST register | 2026-11-11 | New sales invoices | Receivables **+₹3,24,500** |
| 5 | `05-tally-daybook-2026-11-12.xml` | Tally XML | 2026-11-12 | Receipt + payment vouchers | Receivables −INV-1805, payables −PUR-5337 |
| 6 | `06-sales-invoice-INV-1935.pdf` | PDF invoice | 2026-11-12 | Fields read from the PDF with confidence | Receivables +₹1,65,200 ("sales" in the file name books it as a sale; otherwise RUNWAY safely assumes a purchase) |
| 7 | `07-broken-statement-no-dates.csv` | Bank statement | any | Validation | Refused: "no recognisable date column" - nothing written |
| 8 | `08-gstr1-b2b-portal-format.json` | GST register | 2026-11-13 | GST-portal JSON shape | Receivables +₹59,000 |

After each import open **Integrations → Import history → Open**: it shows the
rows that upload added and a before/after table (cash, receivables,
payables, runway, breach probability, health). Every upload stays there; the
ledger only grows, like a bank passbook. "See all rows from this upload"
filters the Transactions screen to that file. Importing the same file twice
adds nothing (duplicates).

**Point-in-time:** after file 1, set the as-of date back to 2026-11-07 - the
PUR-5352 breach is still shown, because on that day it was unpaid.

## Real data

Switch business to **UCI Online Retail II (real data)** and set the as-of date
to **2011-12-09**. 1,107 bank rows built from 887,037 real invoice lines.
Source, licence and every conversion rule: `data/real/uci_online_retail_ii/SOURCE.md`.
`verify.py` there recomputes cash and 30-day flows from the CSV with pandas
and compares them with RUNWAY: they match to the paisa.

## Accounts and approvals

Sign up at **/signup** as Manager or Accountant with the owner's join code
(owner: **Team & approvals** in the sidebar). Manager → owner approves.
Accountant → manager **and** owner approve. Until then the user sees only a
"Waiting for approval" page; every data API returns 403.

Regenerate the files with `make_demo_files.py`; re-check with
`check_demo_imports.py` (instructions at the top of that file).
