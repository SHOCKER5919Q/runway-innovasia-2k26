# Integration status

One principle governs this page, in the product and here:

> An integration is listed as **available** only when it works with no credentials
> beyond a file you already have. Everything else states exactly what it would
> require — credentials, a partner, or eligibility as a regulated entity.

---

## Working today

| Connector | Accepts | What it handles |
|---|---|---|
| **Bank statement CSV** | `.csv`, `.txt` | Auto-detects column layouts across common Indian bank exports. Separate debit/credit columns or a single signed amount both work. Skips preamble rows. Handles `(1,234.00)`, `1,234.00 Dr`, `₹1,234`. |
| **Gateway settlement CSV** | `.csv` | Gross, fee and net. **Credits the invoice with the gross** and books the MDR as a separate expense — the part most tools get wrong, which otherwise leaves every invoice permanently short. |
| **TallyPrime voucher XML** | `.xml` | Receipt and payment vouchers become transactions; sales and purchase vouchers become invoices. Day Book → Export → XML. |
| **GST register JSON/CSV** | `.json`, `.csv` | GSTR-1 style outward and GSTR-2B style inward registers, including taxable value and tax split. |
| **PDF invoice** | `.pdf` | Reads the invoice number, date, GSTIN, taxable value, tax and total. Text-layer PDFs (GST e-invoices, Tally, Zoho, Busy) are read exactly. Scanned images are OCR'd when `tesseract` and `poppler-utils` are installed. **Every field carries its own confidence.** |
| **Manual entry** | — | Transactions, invoices and obligations typed directly. |

Every importer runs the same pipeline: parse → fingerprint → deduplicate → resolve
counterparty → classify → match to invoices, with a **dry-run preview** before
anything is written.

### What the pipeline does with messy data

| Situation | Behaviour |
|---|---|
| Unparseable row | Rejected with its row number and reason, listed in the import report. Never silently skipped. |
| Exact duplicate (same bank reference) | **Rejected**, with the existing transaction named. |
| Possible duplicate (no distinguishing reference) | **Imported and flagged.** A business genuinely can pay the same supplier the same amount twice. |
| Duplicate within the same file | Caught, even on a dry run where nothing has been written yet. |
| Ambiguous counterparty | No match recorded; the reason names both candidates and their scores. |
| Low-confidence category | Written with its confidence and surfaced under "needs review". |
| Gateway fee | Split out as its own expense; the invoice gets the gross. |
| PDF with no readable total | **Refused** with the missing fields named. RUNWAY will not write an invoice it could not read. |
| Scanned PDF, no OCR installed | Refused with instructions, not an obscure failure. |

---

## Built, not connected

| Connector | Status | Required |
|---|---|---|
| **Account Aggregator (RBI / ReBIT)** | `regulated_entity_required` | The operator must be an RBI/SEBI/IRDAI/PFRDA-regulated entity eligible to register as an FIU, or work through one as a Technology Service Provider · an agreement with a licensed NBFC-AA · ReBIT client-standards adoption and Sahamati onboarding · consent artefacts with purpose limitation and revocation |
| **GST returns via a GSP** | `partner_required` | A GSP contract and API credentials · taxpayer OTP or API-key authentication per GSTIN · rate limits and per-return reconciliation rules |
| **Payment gateway webhooks** | `sandbox_required` | Merchant account and webhook secret · a public HTTPS endpoint with signature verification |
| **TallyPrime live connector** | `sandbox_required` | Tally running with the XML gateway enabled · a local agent on the same network |
| **WhatsApp daily briefing** | `partner_required` | WhatsApp Business Cloud API access · templates approved by Meta · a verified business number |
| **TReDS invoice discounting** | `partner_required` | Seller onboarding on a licensed platform · buyer acceptance of each invoice · a platform API agreement |

### What exists for each

- **Account Aggregator** — a ReBIT-shaped payload parser that exercises the real
  ingestion path against sample data. The data model is already correct. Flip the
  adapter on once an FIU arrangement exists. **No claim of live AA connectivity is
  made anywhere in this product.**
- **GST via GSP** — JSON and CSV importers for the same return shapes work today,
  so the schema and reconciliation logic are already proven.
- **Gateway webhooks** — the settlement CSV importer already splits gross, MDR and
  net correctly, which is the hard part.
- **Tally live** — Tally XML exports import today.
- **WhatsApp** — the briefing is generated server-side and is renderable as text,
  which is the prerequisite. The delivery channel is not built.
- **TReDS** — the discounting scenario models advance rate, discount charge,
  platform fee and effective annualised cost so the decision can be evaluated
  before onboarding.

---

## PDF invoices in detail

**Text layer vs scan.** The adapter counts characters per page. Below ~120 it
concludes there is no usable text layer and switches to OCR, saying so in the
import report.

**Per-field confidence.** Each field is extracted by an ordered pattern list, most
specific first, and carries the confidence of the pattern that matched. The import
preview renders each field with its own percentage rather than one number for the
document.

**Cross-checking.** When `taxable + tax` reconciles with the total to within 1%,
all three confidences *rise* — independent corroboration. When they disagree, all
three *fall*, because one of them was misread. With no tax line at all, an 18%
split is assumed at 35% confidence and labelled "assumed 18% GST – verify".

**A real bug this caught.** `CGST 9%: 10,094.19` — the rate comes before the amount.
Matching the first number on the line read the tax as **9**, which then failed to
reconcile. The extractor now strips percentage tokens and takes the rightmost
figure on the line.

**Direction.** A single invoice PDF rarely states whether it is a sale or a purchase
from the holder's point of view. The adapter infers it from the filename, defaults
to *purchase* — the safer error, since a wrongly-created sales invoice would inflate
receivables — and says so in the preview.

## Not built

Nothing from the original specification remains unimplemented. The connectors listed
above as "built, not connected" are blocked on credentials and agreements, not on
code.

---

## The adapter contract

```python
class Adapter(ABC):
    key: str
    label: str
    status: IntegrationStatus     # the honest declaration
    category: str
    description: str
    requirements: list[str]
    accepts: list[str]
    produces: str                 # transactions | invoices | transactions+invoices

    @abstractmethod
    def parse(self, content: bytes, *, filename: str = "")
        -> tuple[list[NormalisedRow | dict], ParseReport]:
        ...
```

Everything downstream consumes `NormalisedRow`. Nothing in the ledger, the
forecaster or the interface knows where a transaction came from, which is why adding
a provider touches exactly one file.

`status` being part of the contract is deliberate: an adapter cannot be added
without declaring what it needs to work, and that declaration is what the
Integrations screen renders.

---

## Try it now

The Integrations screen has a **"Try a sample file"** button for each importer.
The bank sample deliberately contains an exact duplicate row so the duplicate
detector can be seen working:

```csv
Date,Narration,Chq/Ref No,Withdrawal Amt,Deposit Amt,Closing Balance
05/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1807,NEFT993188210,,132346.00,845000.00
05/11/2026,NEFT CR-ABC DISTRIBUTORS-INV-1807,NEFT993188210,,132346.00,845000.00
06/11/2026,GST CHALLAN PMT-06 GSTR-3B OCT 2026,GST202610,269974.00,,575026.00
06/11/2026,NEFT DR-XYZ FOODS PVT LTD-PUR-5231,NEFT771209883,184500.00,,390526.00
07/11/2026,UPI/P2A/418822190034/PAYMENT,,,42000.00,432526.00
```

Expected result: 5 rows seen, 1 duplicate rejected, GST and supplier payments
correctly categorised, ABC Distributors resolved by name, and the bare UPI credit
left **unidentified at 45% confidence** rather than guessed.
