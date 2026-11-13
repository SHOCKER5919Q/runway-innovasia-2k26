# Real dataset: UCI Online Retail II

## Where it came from

| | |
|---|---|
| Dataset | **Online Retail II** — UCI Machine Learning Repository, dataset id 502 |
| Page | https://archive.ics.uci.edu/dataset/502/online+retail+ii |
| File downloaded | https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip |
| Retrieved | 2026-11-13 |
| SHA-256 of the zip | `572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb` |
| Licence | Creative Commons Attribution 4.0 (CC BY 4.0) |
| Citation | Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D |

**What it is:** every transaction of a UK-based, registered, non-store online
retailer selling gift-ware, 1 Dec 2009 – 9 Dec 2011. 1,067,371 invoice lines.
These are real transactions, not synthetic data.

The raw archive is **not committed** (45.6 MB). `download.py` restores it
from the official URL above and refuses any file whose SHA-256 differs.
`raw/` is gitignored.

## What is in this folder

| File | What |
|---|---|
| `download.py` | Fetches the original zip from UCI and verifies its SHA-256 |
| `convert.py` | Deterministic conversion to a RUNWAY bank-statement CSV |
| `bank_statement_inr.csv` | The converted statement (committed) — 1,107 rows |
| `conversion_report.json` | Row counts, totals and hashes from the last conversion |
| `raw/online_retail_ii.zip` | The untouched original (gitignored) |

## How it was converted — every rule

1. **Window:** 1 Apr 2010 – 9 Dec 2011 (FY 2010-11 and FY 2011-12), 20 months.
   This keeps each day inside a financial year for which an RBI average rate
   is published (rule 6).
2. **Duplicates:** 34,335 exact duplicate lines removed. Most come from the
   two worksheets overlapping on 1–9 Dec 2010.
3. **Dropped:** 6 "Adjust bad debt" entries (invoice prefix `A`, bookkeeping,
   not cash) and 4,693 zero-value lines (stock adjustments, price 0).
4. **One row per day per kind**, each the exact sum of that day's lines:
   - *Online sales settlement* (credit) — normal invoices, including postage
     charged to customers.
   - *Customer refunds* (debit) — cancellation invoices (prefix `C`).
   - *Amazon marketplace fee*, *Bank charges*, *CRUK charity commission* —
     the cost lines the shop itself recorded (debit; a positive net is a
     reversal, credit).
5. **Timing assumption:** an online shop is paid at checkout, so each day's
   sales are treated as settling to the bank the same day. Real card
   settlement is usually T+1 or T+2; this shifts cash by a day or two, not
   amounts.
6. **Currency:** GBP converted to INR at the **financial-year average rate**
   from the RBI *Handbook of Statistics on the Indian Economy*, Table 147
   (exchange rate of the rupee vis-à-vis pound sterling; FEDAI indicative
   rates for these years): **₹70.88/£ for FY 2010-11**, **₹76.39/£ for
   FY 2011-12**. The original GBP figure is kept in its own column on every
   row, so the conversion can be checked or undone.
7. **Opening balance:** not in the data. The account opens at ₹0 on
   1 Apr 2010, so "cash" is the cumulative net of the real flows.

## What the data does NOT contain (honest limits)

- **No supplier bills, payroll, rent or tax.** The shop's costs of buying
  stock and running the business are not in the dataset. RUNWAY is not told
  to invent them, so the forecast for this business sees only sales, refunds
  and fees — its runway is long and its breach probability near zero. That is
  what this data supports, not a claim about the real shop's finances.
- **No receivables.** Customers paid at checkout, so there are no open
  invoices, ageing or payment-delay behaviour to model.
- **UK business, 2010–11.** It tests that RUNWAY's pipeline and calculations
  are correct on real transaction patterns (seasonality, the November peak,
  refunds); it is not an Indian MSME.

## How to load it

```
./run.sh seed-real        # creates the "UCI Online Retail II" workspace
```

It is imported through the same pipeline as any uploaded bank statement
(`bank_csv` adapter → dedupe → classify → reconcile). In the app, switch
business to **UCI Online Retail II (real data)** and set the as-of date to
**2011-12-09** in Settings.
