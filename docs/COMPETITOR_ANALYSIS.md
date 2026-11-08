# Competitor analysis

> Based on publicly documented capabilities as of November 2026. These are good
> products; the point of this page is not that they are deficient but that they
> answer **different questions**. Where a capability is uncertain, it is marked as
> such rather than asserted.

---

## The landscape

| Product | What it is | The question it answers |
|---|---|---|
| **TallyPrime** | The default accounting system for Indian SMEs | What did we record? |
| **Vyapar** | Mobile-first billing and inventory | What did we bill and what is in stock? |
| **Zoho Books** | Cloud accounting with a wide app suite | What are our books, accessible anywhere? |
| **Razorpay / Cashfree** | Payment gateways with merchant tooling | Did the payment succeed and when does it settle? |
| **ClearTax** | GST and income-tax compliance | Are we filed correctly and on time? |
| **Khatabook** | Digital ledger for micro businesses | Who owes me, informally? |
| **Lendingkart** | Digital MSME lending | Can this business borrow? |
| **TReDS platforms** | RBI-licensed receivables discounting | Can this invoice be sold? |
| **Account Aggregator ecosystem** | Consent-based data sharing | Can this data move, with permission? |

---

## What each solves well

**TallyPrime** is the system of record. Deep statutory compliance, a vast
accountant base, and entrenched workflows. If an Indian SME has software, it is
probably this.

**Vyapar** made billing and basic inventory genuinely accessible on a phone for
businesses that would never run Tally.

**Zoho Books** brought cloud accounting and a coherent app ecosystem to the segment.

**Payment gateways** solved collection and settlement. The data they produce —
gross, fee, net, settlement date — is clean and structured.

**ClearTax** turned GST compliance from a specialist task into a workflow.

**TReDS** created a regulated market for MSME receivables.

**The AA framework** solved consented data portability at the infrastructure level.
It is the precondition for everything in this category.

---

## What is left over

Not criticisms — these are simply outside what those products set out to do.

**Nobody's answer spans the sources.** Bank data lives at the bank, invoices in
Tally, settlements at the gateway, GST at ClearTax. The owner holds the join in
their head.

**Reporting is backward-looking.** Accounting systems answer "what happened".
Cash-flow forecasting modules, where they exist, typically project a trend. The
question "will I have enough in week eight" needs invoice-level timing, not a
trend line.

**Prediction is scarce, and uncertainty scarcer.** Few tools in this segment predict
*when a specific buyer will pay*. Fewer still publish an uncertainty band. We are
not aware of one that publishes its **measured calibration** — and we would be glad
to be corrected.

**Decisions are unsupported.** "Can I afford this order?" is answered, if at all,
with a margin calculation. The funding gap — the days and rupees between paying for
materials and being paid for goods — is the part that actually decides it.

**Advice precedes the engine.** Lending products assess creditworthiness; they do
not help an owner decide whether borrowing is the right answer at all, or compare it
against collecting overdue invoices for free.

---

## Where RUNWAY sits

| Capability | Accounting systems | Gateways | Lending | RUNWAY |
|---|---|---|---|---|
| Record transactions | **Yes** | Partial | No | Imports them |
| Reconcile across sources | Partial | No | No | **Yes** |
| Per-buyer payment behaviour | Rare | No | Internal only | **Yes, from settled invoices** |
| 13-week cash forecast | Some | No | No | **Yes, invoice-level** |
| Published uncertainty bands | Rare | No | No | **Yes** |
| **Measured** forecast accuracy | Not that we have seen | No | No | **Yes** |
| Decision simulation | No | No | No | **Yes, 12 scenarios** |
| Risk-adjusted option ranking | No | No | No | **Yes** |
| Statutory deadline intelligence | Compliance tools | No | No | **Yes, MSMED + 43B(h)** |
| Explainable AI assistant | Emerging | No | No | **Yes, tool-bound** |

**RUNWAY does not compete on columns 1–3.** It consumes them.

---

## The honest comparison

Things the incumbents do better, and will continue to:

- **Statutory accounting depth.** Tally's compliance coverage is the product of two
  decades. RUNWAY does not attempt it.
- **Billing and inventory workflow.** Vyapar's is better and is the daily tool.
- **Filing.** ClearTax files; RUNWAY estimates a liability and tells you to verify
  it on the portal.
- **Distribution.** Every one of them has more users than RUNWAY will have for
  years.
- **Payment processing.** Not attempted.

Things RUNWAY does that we could not find in the segment:

- Separating actual, predicted and simulated **in the data model**, not just the UI.
- Publishing **measured** forecast accuracy, including the horizons where it is poor.
- Refusing to ship a model that fails a significance test against its own baseline,
  and saying so on screen.
- A copilot whose every figure is **verified against deterministic tool output**
  before display.
- Scheduling payables at the earlier of the contractual and the **MSMED statutory**
  deadline, and refusing to defer protected invoices in a scenario.

---

## Why integration beats replacement

Asking an MSME to migrate from Tally is asking them to take a real risk — retraining
staff, re-entering masters, losing their accountant's familiarity — for a benefit
they cannot evaluate until afterwards.

Asking them to export a file, or eventually to grant AA consent, is asking for
almost nothing. If RUNWAY turns out not to be useful, they stop opening it and
nothing is lost.

That asymmetry is the whole adoption argument, and it is why the integration
framework is built as adapters that consume what exists rather than as a migration
path that replaces it.

---

## What would make this analysis wrong

- An incumbent shipping invoice-level probabilistic forecasting with published
  calibration. Entirely possible; they have the data.
- The AA ecosystem commoditising data access to the point where the integration
  layer stops being differentiating — which would be good for MSMEs and would move
  RUNWAY's value entirely onto the intelligence layer.
- A model good enough that interpretability stops being the constraint. Not yet,
  and not for financial decisions where the owner carries the consequence.
