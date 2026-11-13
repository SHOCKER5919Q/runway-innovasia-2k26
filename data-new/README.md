# data-new: review demo pack (fresh account)

1. Sign up at **/login → Create account** (Owner). Open **Integrations**.
2. Import in this order (the importer is picked automatically if you choose the wrong one):

| # | File | What it builds |
|---|---|---|
| 1 | `1-sales-register.csv` | 6 customers, 127 sales invoices (receivables) |
| 2 | `2-purchase-register.csv` | 4 suppliers, 53 bills (payables) |
| 3 | `3-bank-statement.csv` | 26 weeks of cash; 141 payments settle invoices automatically |
| 4 | `4-bank-statement-2026-11-08.csv` | Next day: 3 customer receipts + 1 supplier payment settle open invoices; the last row is an exact duplicate and is rejected |

After file 4 the dashboard moves to **8 Nov 2026** by itself (it always shows the
latest day in your ledger): receivables and payables drop by the amounts paid.
**Integrations → Import history → Open** shows each file's rows and before/after figures.
Then try the **AI Copilot**: "hi", "should I accept 7 lakh from Sharma Garments?",
"who should I chase today?".

Synthetic data for a fictional textile trader - not a real business.
