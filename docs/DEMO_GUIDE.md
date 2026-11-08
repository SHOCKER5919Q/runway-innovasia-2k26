# Demo guide

## Setup

```bash
./run.sh setup     # ~3 minutes: venv, dependencies, seed
./run.sh dev       # API :8000, web app :3000
```

Open **http://localhost:3000**. The demo clock is pinned to **7 November 2026** so
every figure matches the documentation.

| Account | Password | Role |
|---|---|---|
| `owner@runway.demo` | `demo1234` | Business owner — full access |
| `manager@runway.demo` | `demo1234` | Manager — cannot change policy |
| `ca@runway.demo` | `demo1234` | Chartered accountant — two-client portfolio |

---

## The synthetic business

**Sri Lakshmi Industrial Supplies** — wholesale distribution, Hyderabad, ~₹4.8 crore
annual revenue.

| | |
|---|---|
| History | 18 months (~1,864 transactions, ~1,303 invoices) |
| Accounts | HDFC current, cash in hand, a lien-marked FD |
| Customers | 6, with distinct and *learnable* payment behaviours |
| Suppliers | 10, two offering early-payment discounts |
| Obligations | GST, payroll, rent, utilities, freight, TDS, a term-loan EMI |
| Seasonality | Festive peak Sep–Nov, trough Feb–Mar |

### Deliberately planted, so the engine can be seen working

- **ABC Distributors** — 29% of revenue, drifting from 8 to 22 days late over
  eighteen months. The drift is the point: a flat average would hide it.
- **A double-paid supplier bill** — ₹1,84,500 twice, one day apart, no shared
  reference. The duplicate detector flags it rather than deleting it.
- **Five unidentifiable UPI credits** — bare references with no counterparty.
  They stay unreconciled at 45% confidence rather than being guessed.
- **22% of collections through a payment gateway**, net of MDR, so the gross/fee/net
  reconciliation is exercised on real volume.
- **Partial payments** on ~28% of ABC's invoices.
- **A second business**, Deccan Precision Components (manufacturing, scenario C),
  for the accountant portfolio and the tenant-isolation tests.

Everything is generated from a fixed seed. Nothing is hand-written, and the same
seed reproduces the same workspace exactly.

---

## The four-minute walkthrough

### 1 · Home — the number that is actually true

Available cash: **₹4,77,221**. The bank statements say ₹14,07,195. The difference is
₹5,00,000 lien-marked against the overdraft and ₹4,29,974 already committed to GST
and payroll.

*Say:* "Most dashboards show the bigger number. The business cannot spend it."

### 2 · Customers — behaviour, from settled invoices only

ABC Distributors: 29% of revenue, mean delay **+22.4 days**, reliability 51/100,
**high** risk, ₹40.7 lakh open — from 201 settled invoices.

Click through. The monthly series shows the delay **drifting later**.

*Say:* "Open invoices are excluded from these statistics, because the invoices that
haven't been paid are exactly the ones that are late. Including them would flatter
every customer."

### 3 · Risk Centre — the engine has already joined the dots

Concentration alert, ageing alert, and stress tests showing the business **does not
survive** a 30-day market-wide payment slowdown even after drawing its overdraft.

Expand any alert: what happened, why it matters, the evidence, the likely impact,
what to do, what happens if nothing is done.

### 4 · Scenario Lab — the signature moment

**"Accept a new order."** ₹15 lakh, 18% margin, 60-day terms, no advance.

> ₹15,00,000 order at 18% margin. ₹12,30,000 of materials is payable on day 37,
> while the ₹15,00,000 balance arrives on day 88 — a 51-day funding gap of up to
> ₹12,30,000.

| | Baseline | Scenario |
|---|---:|---:|
| Minimum cash P50 | ₹11,07,339 | ₹2,10,926 |
| Minimum cash P10 | ₹20,341 | −₹11,03,917 |
| Breach probability | 17% | **54%** |

*Say:* "The order is profitable. The question is whether the business can fund 51
days of ₹12.3 lakh."

**Move the advance to 30% and re-run.** Minimum cash ₹6,23,924, breach probability
35%.

*Say:* "Same order. Same margin. Different financing. Both runs used the same random
draws, so the difference is the decision, not the noise."

**Then switch to "Revenue falls" at 20%** and scroll past the main comparison to the
**second-quarter cross-check**:

```
closing cash change at 13 weeks   −₹3,50,530
closing cash change at 26 weeks   −₹7,47,749      impact grows after week 13
```

*Say:* "A 13-week window sees the purchases a revenue drop causes before the
collections they fund, so it understates the damage. Rather than put that in a
footnote, the engine re-runs the comparison over two quarters. The scenario looks
half as bad as it is over one quarter."

### 5 · Optimise — rank the real options

```
Recommended: Discount receivables         utility +0.400   feasible
             Working-capital loan         utility +0.330   feasible
             Accept with 30% advance      utility −0.391   P10 cash goes negative
             Accept, no advance           utility −0.455   P10 negative; breach 56% > 40%
```

*Say:* "Infeasible options are shown with the policy they breach named. The engine
ranks; the owner decides — that sentence is in the API response."

### 6 · Copilot — and what it refuses

> **Should I accept a Rs 15 lakh order on 60-day terms?**

Same numbers, labelled **SIMULATED**, ending with *"Nothing has been written to your
ledger."*

Then:

> **When will invoice INV-999999 be paid?**

> No open invoice matches that description. RUNWAY will not estimate a payment date
> for an invoice it cannot find.

*Say:* "The model never sees the database. It receives the tool's JSON and writes
prose. Every rupee figure in the reply is verified against that JSON before display."

### 7 · The honesty slide — Cash Runway → Method and assumptions

> paired calibration test over 166 invoices: baseline MAE 8.87d, stacked 8.59d at
> w=0.85 (+3.2%, t=+1.29). Learned model **NOT shipped** — the improvement is not
> distinguishable from noise, so RUNWAY uses the per-customer median.

*Say:* "The gradient-boosted model lost to a median, and the product says so on its
own screen. A system that only reports its wins isn't reporting."

---

## The five scenarios

**Settings → Demonstration scenario.** Switching regenerates the entire workspace;
every module recomputes because the data changed. Nothing is hardcoded per scenario.

| | Label | Target cash | What it shows |
|---|---|---:|---|
| **A** | Healthy | ₹14.60 L | Collections near terms, comfortable buffer. The calm case. |
| **B** | Delayed payments | ₹8.24 L | **Default.** Revenue unchanged, cash conversion stretched. The problem appears in ageing before it appears in the bank. |
| **C** | Liquidity crisis | ₹3.10 L | Collections slipping past the month-end obligation cluster. P10 breaches early. |
| **D** | Expansion | ₹11.40 L | Healthy base with an order and an equipment decision on the table. |
| **E** | Adverse conditions | ₹5.80 L | Revenue falling and input costs rising together — the compound shock. |

Compare A and C side by side: same engine, same code paths, different data,
materially different health score, alerts and recommendations.

---

## Showing the integrations honestly

**Integrations → Try a sample file → Preview.**

The bank sample contains a deliberate exact duplicate:

```
5 rows seen · 1 duplicate rejected · GST and supplier payments categorised ·
ABC Distributors resolved by name · the bare UPI credit left unidentified at 45%
```

Then scroll to **"Declared, not claimed"**. Each connector states what it would
require — including that an Account Aggregator FIU arrangement needs the operator to
be an RBI/SEBI/IRDAI/PFRDA-regulated entity.

*Say:* "We built the adapter and parsed sample payloads. We are not connected, and
the product doesn't pretend to be."

### PDF invoices

Switch the source to **PDF invoice** and drop in any invoice PDF. The preview shows
**each field with its own confidence** rather than one number for the document:

```
Invoice No   INV-1807          95%     Taxable   1,12,157.63   99%
Issue Date   2026-11-05        95%     Tax         20,188.37   95%
GSTIN        36ABCDE1234F1Z5   98%     Total     1,32,346.00   99%
```

*Say:* "Taxable plus tax reconciles with the total to within a rupee, so all three
confidences went **up** — that is independent corroboration, not a guess. When they
disagree, all three go down. And a PDF it cannot read is refused with the missing
fields named, rather than a half-read invoice entering the ledger."

Worth mentioning: `CGST 9%: 10,094.19` once extracted the tax as **9**, because the
rate comes before the amount on the line. The test that catches it is
`test_a_tax_rate_is_not_mistaken_for_a_tax_amount`.

---

## The accountant view

Sign in as `ca@runway.demo`. Two clients, ordered by how much attention they need,
with exceptions surfaced rather than a wall of numbers. Only businesses that granted
access appear — the owner account gets a **403** on the second business, and there
is a test asserting it.

---

## Verifying the claims live

```bash
./run.sh verify        # 4,996 accounting invariants
./run.sh test          # 210 backend tests on SQLite
./run.sh test-pg       # the identical suite on PostgreSQL
./run.sh test-web      # 75 frontend tests
./run.sh audit-schema  # every VARCHAR against what the code can write
./run.sh evaluate      # regenerates every published accuracy figure
```

Running `verify` in front of an audience is worth the thirty seconds. It prints the
balance identity for every account and ends with *"All accounting invariants hold."*

`test-pg` is the other one worth showing: the same suite, a completely different
database engine, same result. Mention that getting there found three `VARCHAR`
overflows SQLite silently tolerates — two of which the demo data never exercised —
and that `audit-schema` now makes that class of bug impossible to reintroduce.

---

## Questions worth being ready for

**"Is this real data?"** No, and it says so on every screen, in the API and in the
shared report. The generator is `backend/app/seed/generator.py` and it is seeded.

**"How do you know the forecast is any good?"** We measure it. Business State Centre
→ Predicted shows coverage by horizon with the sample size, and reports that
long-horizon coverage is poor.

**"What stops the AI making something up?"** Three things: it never sees the
database, it only receives tool output, and every rupee figure in its reply is
checked against that output before display. There is a test that feeds it a
fabricated figure and asserts the reply is rejected.

**"Why isn't your ML model better?"** It isn't, on this data, and the product says
so. The per-customer median is near-optimal when delays are close to i.i.d. per
customer. What we built is the machinery that *detects* that and refuses to ship the
complex model — which is the part that transfers to real data.

**"Could I use this tomorrow?"** You could import a bank CSV or a PDF invoice
tomorrow and get a reconciled ledger, a forecast and a scenario lab. You could not
connect it to your bank automatically — that needs an FIU arrangement, and
`docs/INTEGRATION_STATUS.md` says exactly what that involves.

**"Does it run on a real database?"** Yes, and it is checked rather than claimed.
`./run.sh test-pg` runs the identical suite against PostgreSQL. SQLite is the
default only so the project starts with one command.
