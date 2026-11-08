# Compliance notes

What RUNWAY implements, what it only reports, and what it explicitly does not claim.

> **Not legal or tax advice.** These notes record how the engine behaves and why.
> Verify any position against the statute and a professional before relying on it.

---

## MSMED Act 2006, Section 15 — the payment window

**The rule.** A buyer must pay a supplier that is a registered **micro or small**
enterprise within the agreed period. Where there is a written agreement, that period
**cannot exceed 45 days**. Where there is no written agreement, the limit is
**15 days** from acceptance of the goods or services. Medium enterprises are outside
the rule.

**Implemented** in `app/analytics/payables.py::msmed_deadline`:

```python
if supplier.msme_class not in {"micro", "small"}:
    return None                                   # out of scope
limit  = 45 if invoice.has_written_agreement else 15
agreed = min(invoice.credit_days, limit)
return invoice.issue_date + timedelta(days=agreed)
```

**Consequences in the engine:**
- The forecast schedules a protected payable at `min(contractual_due, statutory_deadline)`.
- The scenario engine **refuses** to defer a protected invoice unless the owner
  explicitly turns the protection off, and warns when they do.
- Exposure is reported as three figures: covered outstanding, already breached, and
  due within 14 days.

**Caveat carried in the product:** classification depends on the MSME class recorded
against each supplier. Confirm Udyam registration before relying on it.

---

## Income-tax Act, Section 43B(h) — deduction timing

**The rule.** Inserted by the Finance Act 2023, effective from FY 2023-24. An amount
payable to a micro or small enterprise is deductible **only in the year it is
actually paid**, where payment falls outside the MSMED §15 window. Unlike other
43B items, paying before the return due date does **not** preserve the deduction for
the earlier year.

A Ministry of Finance reply dated 21 July 2026 confirmed the timeline cannot exceed
45 days. Commentary notes the provision moves to Section 37(2)(g) of the Income-tax
Act, 2025 from tax year 2026-27.

**Implemented as reporting, not as a tax computation.** RUNWAY surfaces the exposure
and prioritises those invoices in recommendations. It does not compute a
disallowance, does not file anything, and says so.

---

## GST — GSTR-3B estimation

**What RUNWAY does.** Estimates the monthly liability as:

```
estimated liability = output GST on recorded sales
                    − input credit on recorded purchases
```

paid by the 20th of the following month for monthly filers.

**Everywhere this number appears it is labelled an estimate**, with the basis shown:
output tax, input credit and the fact it has not been verified.

**Not modelled:** QRMP quarterly filers, reverse charge, ineligible ITC under s.17(5),
amendments and credit notes crossing periods, TDS/TCS under GST, e-invoice IRN
validation, and the distinction between GSTR-1, GSTR-2B and GSTR-3B reconciliation.

**The product's position:** confirm the liability on the GST portal before paying.
That sentence appears on the Compliance screen and in the API response.

---

## RBI Account Aggregator framework

**What it is.** A consent-based data-sharing framework. A Financial Information User
(FIU) requests data; a licensed NBFC-AA brokers the consent; a Financial Information
Provider (FIP) supplies it. ReBIT publishes the API specifications (AA API, FIP API,
FIU Callback API). The RBI recognised Sahamati as the ecosystem's self-regulatory
organisation in June 2026.

**Eligibility — the part that matters here.** An FIU must be a **regulated entity**.
An organisation not registered with the RBI, SEBI, IRDAI or PFRDA cannot be an FIU
directly; it must work through one, typically as a Technology Service Provider.
Sahamati's own FAQ states that eligibility is set by notifications from each
respective regulator.

**What RUNWAY has.** An adapter that parses ReBIT-shaped deposit FI payloads, so the
ingestion path is built and exercised against sample data.

**What RUNWAY does not have, and says so.** Any live connection. The Integrations
screen marks it `regulated_entity_required` and lists the prerequisites: regulated-
entity eligibility or a TSP arrangement, an agreement with a licensed NBFC-AA, ReBIT
client-standards adoption, Sahamati onboarding, and consent artefacts with purpose
limitation and revocation.

**No screen, no API response and no document in this project claims live AA
connectivity.**

---

## DPDP Act 2023

**Relevant obligations** and where RUNWAY stands:

| Obligation | Status |
|---|---|
| Purpose limitation | Modelled — `consents` carries a purpose and a scope, not a blanket grant |
| Consent for processing | Modelled for data sharing; the AA consent flow is not built |
| Right to erasure | **Not implemented.** Needs a defined, auditable deletion path with statutory retention carve-outs |
| Data minimisation | Implemented — no credentials, masked account numbers, no PAN or Aadhaar |
| Security safeguards | Partially — see `SECURITY.md` for the gaps |
| Breach notification | Not implemented |
| Consent manager registration | Not applicable at this stage |

---

## TReDS

An RBI-licensed electronic platform for discounting MSME receivables. Requires
seller onboarding, buyer acceptance of each invoice, and a platform agreement.

**RUNWAY models the economics** — advance rate, discount charge, platform fee,
effective annualised cost — so the decision can be evaluated before onboarding. It
is **not connected**, and the scenario carries a disclaimer that eligibility depends
on buyer acceptance and is not modelled.

---

## Digital lending

RUNWAY does **not** lend, arrange credit, broker a loan, or share data with a
lender without an explicit consent record.

The financing scenario models cost and repayment so an owner can compare options.
Every financing output carries: *"RUNWAY does not arrange credit and cannot predict
whether any lender will approve this facility."*

---

## What RUNWAY explicitly does not claim

| | |
|---|---|
| A credit score or rating | The health score is RUNWAY's own transparent indicator. Not a bureau product, no regulatory standing. The disclaimer travels into the API, the UI and the shared report. |
| Live AA / GST / TReDS connectivity | Nothing is connected. Each connector states what it would need. |
| A regulated VaR | Liquidity VaR is an operational measure adapted from market risk, labelled as such in the output. |
| Tax or legal advice | Deadlines and exposure are surfaced from the ledger. Nothing more. |
| Loan approval | Never implied, in any scenario, anywhere. |
| An accuracy figure it has not measured | Where nothing has matured, the product reports that nothing has matured. |

---

## Sources

These were consulted during research in November 2026. Several are third-party
commentary; the statutes and the regulators' own publications should be checked
before relying on any of it.

- [ReBIT — Account Aggregator ecosystem API specifications](https://api.rebit.org.in)
- [Sahamati — FAQ on FIU/FIP eligibility](https://sahamati.org.in/faq/)
- [Sahamati — FI types available on AA](https://sahamati.org.in/data-fi-types-available-on-aa/)
- [Treelife — NBFC Account Aggregator licence: eligibility and RBI approval](https://treelife.in/fintech/nbfc-account-aggregator-licence/)
- [eCorpIT — Account Aggregator integration in 2026: consent architecture, DPDP overlap, the SRO](https://ecorpit.com/account-aggregator-integration-fintech-builders-2026/)
- [TaxGuru — Section 43B(h) MSME payment](https://www.taxguru.in/income-tax/section-43bh-msme-payment.html)
- [TaxGuru — Finance Ministry clarifies the Section 43B(h) 45-day rule](https://taxguru.in/income-tax/finance-ministry-clarifies-section-43bh-45-day-msme-payment-rule.html)
- [Busy — Section 43B(h): the MSME payment rule and the 45-day limit](https://busy.in/accounting/section-43bh-msme-payment-rule-and-45-day-limit-explained/)
- [India Briefing — Clause (h) of Section 43B and its impact](https://www.india-briefing.com/news/understanding-clause-h-of-section-43b-and-its-impact-on-indias-tax-framework-for-businesses-31205.html/)
- [Tally Solutions — MSME payment rule changes from 1 April 2024](https://tallysolutions.com/gst/msme-payment-rule-changes)
