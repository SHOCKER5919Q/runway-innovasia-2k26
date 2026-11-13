# What changed on `main-1`

Base: `pr2-review` (main + PR #2 Grove v3 UI + landing-figure fixes) + the
team PR fixing the Scenario Lab, risk-alert keys and Windows dates.

## New
- **Roles and approvals** - `/signup` for owner / manager / accountant;
  join codes; manager needs owner approval, accountant needs manager **and**
  owner; pending users see only `/pending` and get 403 on every data API.
  **Team & approvals** screen. Separate menus per role (accountant sees the
  books, not scenario planning or settings). Migration `b7e1c0a4f2d1`
  (existing members back-filled as approved). Tests: `tests/test_approvals.py`.
- **AI copilot models** - xkiro provider, model picker, per-analysis Auto,
  benchmark-backed guide, free-quota handling. See `COPILOT_MODELS.md`.
- **Import history** - every upload records before/after figures; open any
  past upload to see its rows and what it changed; Transactions filter by
  upload. Ledger stays append-only; re-uploads are duplicates.
- **Real dataset** - UCI Online Retail II (CC BY 4.0) with source, hash,
  converter, verifier and `./run.sh seed-real`. See
  `data/real/uci_online_retail_ii/SOURCE.md`.
- **Demo import files** - 8 files (CSV, Excel, Razorpay, GST CSV/JSON, Tally,
  PDF, a broken file) + checker. See `DEMO_IMPORTS.md`.
- **Excel (.xlsx) bank statements** accepted.
- **History requirements** - `DATA_HISTORY_REQUIREMENTS.md`.

## Fixed (each found by testing, not assumed)
1. Dashboard failed on first load after a server start ("database is
   locked"): 30 s SQLite wait + one bundle build per business.
2. Scenario Lab verdict counted tiny changes; now ignores immaterial moves,
   says **mixed** when the downside worsens, and defers to the 26-week view.
3. Scenario Lab baseline (2,500 paths) disagreed with the dashboard (4,000).
4. Forecast assumed zero future sales for businesses without invoices
   (shops paid at checkout); now falls back to bank receipts.
5. Bank CSV missed "Withdrawal (INR)" / "Reference" headers.
6. Copilot verifier rejected correct answers (zero stripping, escaped ₹).
7. Past as-of views were rewritten by later payments (receivables,
   payables, MSMED, customer delays now point-in-time).
8. Payments to suppliers named "...Logistics" never settled their bill.
9. Committing a PDF invoice import always crashed (date in JSON).
10. GSTR-1 "b2b" files were booked as purchases.
11. GST imports stored party names in the GSTIN field.
12. Recurring costs understated ~3x for ledgers shorter than 26 weeks.

## Verified
Backend tests, frontend type-check/tests/build, `verify.py` on real data
(4/4, exact to the paisa), demo import checker (12/12).
