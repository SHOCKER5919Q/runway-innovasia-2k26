# Digital twin demonstration

A four-minute walkthrough that shows every layer of the twin doing real work.
Sign in as `owner@runway.demo` / `demo1234`.

---

## Step 1 — The state (Home, 30 s)

The briefing opens with **available cash: ₹4,77,221**. The bank statements say
₹14,07,195. The difference is ₹5,00,000 lien-marked against the overdraft and
₹4,29,974 already committed to GST and payroll.

Most dashboards would show the larger number.

Below it, the 13-week projection with its P10–P90 band, and the safety buffer drawn
as a labelled reference line so the curve is read against the threshold that matters
rather than against zero.

---

## Step 2 — The relationship map (Digital Twin → Relationship map, 40 s)

66 nodes, 65 edges. Customers left, suppliers right, accounts above, obligations
below; node size is open exposure.

The insights underneath are generated, not written:

> ABC Distributors carries the largest open exposure at ₹40,74,629 across 43 invoices.
> ABC Distributors has the most overdue money at ₹17,61,963.
> XYZ Foods Pvt Ltd is the largest open payable at ₹8,74,033.
> The equivalent of 5.1 equally-sized counterparties carry this book. The largest
> single counterparty is 29% of volume.

---

## Step 3 — The timeline (Digital Twin → Future timeline, 40 s)

Every expected event, each labelled with its certainty:

- **actual** — recorded and reconciled
- **contractual** — a known commitment with a fixed date
- **estimated** — derived by RUNWAY, not from a filed document
- **predicted** — a model estimate with a P10–P90 date range

The weekly roll-up adds a **predicted share** per week. A week that is 90% predicted
is far less certain than its total suggests, and the table says so.

---

## Step 4 — The behaviour model (Customers, 40 s)

ABC Distributors: 29% of revenue, mean delay **+22.4 days**, reliability 51/100,
**high** risk, ₹40.7 lakh open.

Click through. The monthly series shows the delay **drifting later** over eighteen
months — a deterioration an average would hide. Every figure comes from 201 settled
invoices; open invoices are excluded, because the invoices that have not been paid
are exactly the ones that are late.

---

## Step 5 — The consequence (Risk Centre, 40 s)

The engine has already connected those facts:

- A buyer concentration alert — 29% against a 35% policy limit.
- A receivables-ageing alert.
- Stress tests: the business **does not survive** a 30-day market-wide payment
  slowdown, or the loss of its largest customer, even after drawing the overdraft.

Each alert answers all six questions: what happened, why it matters, the evidence,
the likely impact, what to do, and what happens if nothing is done.

---

## Step 6 — The decision (Scenario Lab, 90 s)

**"Accept a new order."** ₹15 lakh, 18% margin, 60-day terms, no advance.

RUNWAY does not answer with the profit. It answers with the funding gap:

> ₹15,00,000 order at 18% margin. ₹12,30,000 of materials is payable on day 37,
> while the ₹15,00,000 balance arrives on day 88 — a 51-day funding gap of up to
> ₹12,30,000.

| Metric | Baseline | Scenario |
|---|---:|---:|
| Minimum cash P50 | ₹11,07,339 | ₹2,10,926 |
| Minimum cash P10 | ₹20,341 | −₹11,03,917 |
| Runway P50 | 13.0 wk | 10.8 wk |
| Breach probability | 17% | **54%** |

**Now move the advance slider to 30%** and re-run. Minimum cash recovers to ₹6.24L
and the breach probability drops to 35%. Same order. Same margin. Different
financing.

Both runs used the same seed and therefore the same simulated futures, so the
difference is the decision — stated under the table in those words.

---

## Step 7 — The comparison (Scenario Lab → Optimise, 40 s)

Rank four options on one risk-adjusted objective:

```
Recommended: Discount receivables            utility +0.400   feasible
             Working-capital loan            utility +0.330   feasible
             Accept with 30% advance         utility −0.391   P10 cash goes negative
             Accept, no advance              utility −0.455   P10 negative;
                                                              breach 56% > 40% limit
```

Infeasible options are shown with the policy they breach named. The caveat below
says plainly that the engine ranks and the owner decides.

---

## Step 8 — The conversation (AI Copilot, 40 s)

> **Should I accept a Rs 15 lakh order on 60-day terms?**

Same numbers, labelled **SIMULATED**, ending with:

> Nothing has been written to your ledger. This is a simulation.

Then ask something it cannot answer:

> **When will invoice INV-999999 be paid?**

> No open invoice matches that description. RUNWAY will not estimate a payment date
> for an invoice it cannot find.
>
> I will not estimate a figure I cannot source from your ledger or from a completed
> forecast run.

---

## Step 9 — The feedback loop (Business State Centre → Predicted, 30 s)

> At horizons up to 4 weeks the P10–P90 band contained the actual outcome 100% of
> the time against an 80% target. Beyond 6 weeks coverage falls to 50% over only 4
> observations, so the long-horizon band is both less reliable and too thinly
> measured to draw a conclusion from.

A product that measures its own forecasts and reports the bad horizons is doing
something most do not.

---

## Switching scenarios

**Settings → Demonstration scenario.** Five synthetic businesses, each regenerating
the entire workspace:

| | | What it demonstrates |
|---|---|---|
| **A** | Healthy | Stable collections, comfortable buffer — the calm case |
| **B** | Delayed payments | The default. One large buyer drifting later |
| **C** | Liquidity crisis | Multiple receivables slipping past the obligation cluster |
| **D** | Expansion | Healthy base with an order and an equipment decision on the table |
| **E** | Adverse conditions | Revenue falling and input costs rising together |

Nothing is hardcoded per scenario. Switching regenerates the ledger and **every
module recomputes** — health score, alerts, forecasts, recommendations and the
copilot's answers all change because the underlying data changed.
