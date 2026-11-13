# Starter pack: bring a new account fully to life

**How customers and suppliers are added:** you never type them in. They are
created from the files you import:
- a **sales register** (CSV with a `Customer Name` column) creates the
  customers and their invoices (receivables);
- a **purchase register** (same format with a `Supplier Name` column) creates
  the suppliers and their bills (payables);
- a **bank statement** whose narrations cite those invoice numbers settles
  them - that builds payment behaviour, reliability, cash, forecast and risk.

## Upload these 3 files, in this order

Files are in `data/starter-pack/` (synthetic data for a fictional textile
trader, 26 weeks May-Nov 2026). Sign up as an **Owner**, open
**Integrations**, keep the as-of date **2026-11-07** (Settings), and for each
file pick the adapter, the account, then **Import**.

| # | File | Adapter | Creates |
|---|---|---|---|
| 1 | `1-sales-register.csv` | GST invoice register | 6 customers, 127 sales invoices |
| 2 | `2-purchase-register.csv` | GST invoice register | 4 suppliers, 53 bills |
| 3 | `3-bank-statement.csv` | Bank statement | 168 rows; 141 settle invoices automatically |

Order matters: invoices first, then the bank statement that pays them.

## What you will see (tested on a fresh account)

Cash ₹81,40,709 · receivables ₹58,26,450 · payables ₹18,24,375 · health 76 ·
Customers page: Mehta Fashion House *critical* (61 days late on average),
Lakshmi Fabrics *high*, four reliable payers · Suppliers page: four suppliers
with outstanding balances · forecast, Scenario Lab, Risk Centre and copilot
all working.

Regenerate with `backend/.venv/bin/python data/starter-pack/make_starter_pack.py`.
