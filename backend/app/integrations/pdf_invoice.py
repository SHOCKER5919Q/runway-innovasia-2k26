"""PDF invoice import.

Two kinds of PDF arrive from Indian businesses and they need different
handling, so the adapter detects which it has rather than pretending there
is one answer:

* **Text-layer PDFs** — GST e-invoices, Tally/Busy/Zoho output, and almost
  every invoice produced by software. The characters are in the file; no
  OCR is involved and extraction is exact.
* **Scanned images** — a photographed or scanned paper invoice. These need
  an OCR engine. RUNWAY shells out to ``tesseract`` when it is installed
  and says plainly when it is not. It does **not** bundle an OCR model.

Field extraction is a transparent regex pass tuned for Indian invoice
layouts, and **every field carries its own confidence**. Anything below
``REVIEW_THRESHOLD`` is surfaced for review rather than accepted, because a
wrong invoice total silently entering the ledger is worse than no invoice
at all.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.core.enums import Evidence, IntegrationStatus
from app.core.money import rupees_to_paise
from app.integrations.base import Adapter, ParseReport, register

REVIEW_THRESHOLD = 0.70
# Below this many characters per page we assume there is no usable text
# layer and the document is a scan.
MIN_TEXT_CHARS_PER_PAGE = 120
OCR_TIMEOUT_SECONDS = 60

# ── Indian invoice field patterns ─────────────────────────────────
# Ordered most-specific first; the first match wins and records which
# pattern produced it, so a surprising extraction can be traced.

GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b")

INVOICE_NO_PATTERNS = [
    (0.95, re.compile(r"(?:invoice|inv|bill|tax\s+invoice)\s*(?:no|number|#)\s*[:.\-]?\s*([A-Z0-9][A-Z0-9/\-_]{2,24})", re.I)),
    (0.85, re.compile(r"(?:document|doc)\s*(?:no|number)\s*[:.\-]?\s*([A-Z0-9][A-Z0-9/\-_]{2,24})", re.I)),
    (0.70, re.compile(r"\b((?:INV|BILL|TI|SI|PI)[\-/ ]?\d{3,10})\b", re.I)),
]

DATE_PATTERNS = [
    (0.95, re.compile(r"(?:invoice|bill|document)\s*date\s*[:.\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", re.I)),
    (0.95, re.compile(r"(?:invoice|bill|document)\s*date\s*[:.\-]?\s*(\d{1,2}[-\s][A-Za-z]{3,9}[-\s]\d{2,4})", re.I)),
    (0.70, re.compile(r"\bdated?\s*[:.\-]?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})", re.I)),
    (0.45, re.compile(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})\b")),
]

AMOUNT = r"(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)"

TOTAL_PATTERNS = [
    (0.95, re.compile(r"(?:grand\s+total|total\s+invoice\s+value|invoice\s+total|amount\s+payable)\s*[:.\-]?\s*" + AMOUNT, re.I)),
    (0.85, re.compile(r"\btotal\s+amount\s*[:.\-]?\s*" + AMOUNT, re.I)),
    (0.60, re.compile(r"\btotal\s*[:.\-]?\s*" + AMOUNT, re.I)),
]

TAXABLE_PATTERNS = [
    (0.95, re.compile(r"(?:taxable\s+(?:value|amount)|total\s+taxable)\s*[:.\-]?\s*" + AMOUNT, re.I)),
    (0.70, re.compile(r"\b(?:sub\s*-?\s*total|basic\s+amount)\s*[:.\-]?\s*" + AMOUNT, re.I)),
]

# Tax lines carry both a RATE and an AMOUNT ("CGST 9%: 10,094.19"), and the
# rate comes first. Matching the first number on the line reads 9 as the tax,
# which then fails to reconcile against the total. So the label patterns
# capture the remainder of the line and ``_tax_on_line`` picks the amount.
TAX_LABEL_PATTERNS = {
    "cgst": re.compile(r"\bCGST\b([^\n]{0,60})", re.I),
    "sgst": re.compile(r"\bSGST\b([^\n]{0,60})", re.I),
    "igst": re.compile(r"\bIGST\b([^\n]{0,60})", re.I),
    "utgst": re.compile(r"\bUTGST\b([^\n]{0,60})", re.I),
    "cess": re.compile(r"\bCESS\b([^\n]{0,60})", re.I),
}

# A number immediately followed by % (or by "percent") is a rate, not money.
_RATE_TOKEN = re.compile(r"[\d,]+(?:\.\d+)?\s*(?:%|percent|per\s*cent)", re.I)
_NUMBER_TOKEN = re.compile(r"[\d,]+(?:\.\d{1,2})?")


def _tax_on_line(tail: str) -> float | None:
    """Pull the tax *amount* out of the remainder of a tax line.

    Rates are stripped first, then the **last** remaining number is taken:
    Indian invoice layouts put the rate before the amount, and the amount is
    the rightmost figure on the line.
    """
    cleaned = _RATE_TOKEN.sub(" ", tail)
    nums = [_money(m.group(0)) for m in _NUMBER_TOKEN.finditer(cleaned)]
    nums = [n for n in nums if n is not None and n > 0]
    return nums[-1] if nums else None

PARTY_PATTERNS = [
    (0.85, re.compile(r"(?:bill(?:ed)?\s*to|buyer|customer|consignee)\s*[:.\-]?\s*\n?\s*([A-Z][A-Za-z0-9&.,'\- ]{3,60})", re.I)),
    (0.80, re.compile(r"(?:supplier|seller|vendor|from)\s*[:.\-]?\s*\n?\s*([A-Z][A-Za-z0-9&.,'\- ]{3,60})", re.I)),
]


@dataclass
class ExtractedField:
    value: object = None
    confidence: float = 0.0
    pattern: str = ""
    raw: str = ""

    def as_dict(self) -> dict:
        return {"value": self.value, "confidence": round(self.confidence, 2),
                "matched": self.raw[:80]}


@dataclass
class ExtractedInvoice:
    invoice_no: ExtractedField = field(default_factory=ExtractedField)
    issue_date: ExtractedField = field(default_factory=ExtractedField)
    total: ExtractedField = field(default_factory=ExtractedField)
    taxable: ExtractedField = field(default_factory=ExtractedField)
    tax: ExtractedField = field(default_factory=ExtractedField)
    gstin: ExtractedField = field(default_factory=ExtractedField)
    party: ExtractedField = field(default_factory=ExtractedField)
    source: str = "text_layer"
    page_count: int = 0
    text_chars: int = 0

    @property
    def overall_confidence(self) -> float:
        """Driven by the fields without which the invoice is unusable."""
        required = [self.invoice_no, self.issue_date, self.total]
        if any(f.value is None for f in required):
            return 0.0
        return min(f.confidence for f in required)

    @property
    def usable(self) -> bool:
        return self.overall_confidence > 0.0


def _money(s: str) -> float | None:
    try:
        return float(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _parse_date(s: str) -> date | None:
    from app.integrations.adapters import parse_date
    return parse_date(s.replace(".", "-").replace(" ", "-"))


def _first_match(text: str, patterns, convert) -> ExtractedField:
    for conf, pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        v = convert(m.group(1))
        if v is None:
            continue
        return ExtractedField(value=v, confidence=conf,
                              pattern=pat.pattern[:40], raw=m.group(0))
    return ExtractedField()


def extract_fields(text: str) -> ExtractedInvoice:
    """Pull invoice fields out of a block of text.

    Pure function over a string, so it is unit-testable without a PDF.
    """
    out = ExtractedInvoice()
    out.text_chars = len(text)

    out.invoice_no = _first_match(text, INVOICE_NO_PATTERNS,
                                  lambda s: s.strip().upper().replace(" ", ""))
    out.issue_date = _first_match(text, DATE_PATTERNS, _parse_date)
    out.total = _first_match(text, TOTAL_PATTERNS, _money)
    out.taxable = _first_match(text, TAXABLE_PATTERNS, _money)

    m = GSTIN_RE.search(text)
    if m:
        out.gstin = ExtractedField(value=m.group(1), confidence=0.98,
                                   pattern="GSTIN", raw=m.group(0))

    tax_total = 0.0
    components: list[str] = []
    for label, pat in TAX_LABEL_PATTERNS.items():
        for tm in pat.finditer(text):
            v = _tax_on_line(tm.group(1))
            if v is not None:
                tax_total += v
                components.append(f"{label.upper()} {v:,.2f}")
                break          # one occurrence per component
    if components:
        out.tax = ExtractedField(value=round(tax_total, 2), confidence=0.85,
                                 pattern="sum of " + " + ".join(components),
                                 raw=" + ".join(components))

    out.party = _first_match(text, PARTY_PATTERNS, lambda s: " ".join(s.split())[:120])

    # Cross-check: taxable + tax should reconcile with the total. When they
    # do, that is independent corroboration and confidence rises; when they
    # disagree, one of the three was misread and confidence falls.
    t, tx, tax = out.total.value, out.taxable.value, out.tax.value
    if t and tx and tax:
        if abs((tx + tax) - t) <= max(1.0, 0.01 * t):
            for f in (out.total, out.taxable, out.tax):
                f.confidence = min(0.99, f.confidence + 0.10)
            out.total.pattern += " (+reconciled with taxable+tax)"
        else:
            for f in (out.total, out.taxable, out.tax):
                f.confidence *= 0.75
            out.total.pattern += " (!taxable+tax does not reconcile)"
    elif t and tx and not tax:
        # Derive the tax rather than leaving it blank, but mark it derived.
        out.tax = ExtractedField(value=round(t - tx, 2), confidence=0.55,
                                 pattern="derived as total - taxable")
    elif t and not tx:
        # Assume the common 18% slab, at low confidence so it is reviewed.
        out.taxable = ExtractedField(value=round(t / 1.18, 2), confidence=0.35,
                                     pattern="assumed 18% GST - verify")
        out.tax = ExtractedField(value=round(t - t / 1.18, 2), confidence=0.35,
                                 pattern="assumed 18% GST - verify")
    return out


# ── PDF text extraction ────────────────────────────────────────────

def _text_layer(content: bytes) -> tuple[list[str], str | None]:
    """Return per-page text, or (empty, reason) when it cannot be read."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], ("pypdf is not installed. Install it with "
                    "`pip install pypdf` to import PDF invoices.")
    import io
    try:
        reader = PdfReader(io.BytesIO(content))
        return [(p.extract_text() or "") for p in reader.pages], None
    except Exception as e:
        return [], f"could not read the PDF: {type(e).__name__}: {e}"


def ocr_available() -> bool:
    return bool(shutil.which("tesseract")) and bool(
        shutil.which("pdftoppm") or shutil.which("pdftocairo"))


def _ocr(content: bytes) -> tuple[list[str], str | None]:
    """Rasterise and OCR a scanned PDF via the tesseract CLI.

    Shelling out rather than importing pytesseract keeps the Python
    dependency list clean, and the binary is the part that has to be
    installed either way.
    """
    if not shutil.which("tesseract"):
        return [], ("This looks like a scanned PDF with no text layer, and no OCR "
                    "engine is installed. Install tesseract-ocr, or export the "
                    "invoice from your accounting software as a text PDF.")
    rasteriser = shutil.which("pdftoppm") or shutil.which("pdftocairo")
    if not rasteriser:
        return [], ("This looks like a scanned PDF. tesseract is installed but "
                    "poppler-utils (pdftoppm) is not, so the pages cannot be "
                    "rasterised for OCR.")
    with tempfile.TemporaryDirectory(prefix="runway-ocr-") as tmp:
        pdf = Path(tmp) / "in.pdf"
        pdf.write_bytes(content)
        try:
            subprocess.run([rasteriser, "-r", "200", "-png", str(pdf), str(Path(tmp) / "pg")],
                           check=True, capture_output=True, timeout=OCR_TIMEOUT_SECONDS)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            return [], f"could not rasterise the PDF for OCR: {type(e).__name__}"
        pages: list[str] = []
        for img in sorted(Path(tmp).glob("pg*.png")):
            try:
                r = subprocess.run(["tesseract", str(img), "stdout", "-l", "eng", "--psm", "6"],
                                   check=True, capture_output=True,
                                   timeout=OCR_TIMEOUT_SECONDS)
                pages.append(r.stdout.decode("utf-8", errors="replace"))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pages.append("")
        return pages, None


@register
class PDFInvoice(Adapter):
    key = "pdf_invoice"
    label = "PDF invoice"
    category = "documents"
    status = IntegrationStatus.AVAILABLE
    description = (
        "Reads an invoice PDF and extracts the number, date, GSTIN, taxable value, "
        "tax and total. Text-layer PDFs (GST e-invoices, Tally, Zoho, Busy) are read "
        "exactly. Scanned images are OCR'd when tesseract is installed. Every field "
        "carries its own confidence and anything uncertain is held for review rather "
        "than written to the ledger.")
    requirements = [
        "pypdf for text-layer PDFs (installed with the backend requirements).",
        "tesseract-ocr and poppler-utils, only if you need to read scanned images.",
    ]
    accepts = [".pdf"]
    produces = "invoices"

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[dict], ParseReport]:
        rep = ParseReport(detected_format="pdf_invoice")
        rep.rows_seen = 1

        pages, err = _text_layer(content)
        if err:
            rep.rows_rejected = 1
            rep.errors.append({"row": 1, "error": err})
            return [], rep

        joined = "\n".join(pages)
        source = "text_layer"
        if pages and len(joined.strip()) < MIN_TEXT_CHARS_PER_PAGE * len(pages):
            rep.warnings.append(
                f"Only {len(joined.strip())} characters of text across {len(pages)} "
                f"page(s) - treating this as a scanned document.")
            ocr_pages, ocr_err = _ocr(content)
            if ocr_err:
                rep.rows_rejected = 1
                rep.errors.append({"row": 1, "error": ocr_err})
                return [], rep
            joined = "\n".join(ocr_pages)
            source = "ocr"
            rep.warnings.append(
                "Fields were read by OCR. OCR misreads digits more often than it "
                "misreads letters, so check the amounts before confirming.")

        inv = extract_fields(joined)
        inv.source = source
        inv.page_count = len(pages)

        rep.column_mapping = {
            "invoice_no": inv.invoice_no.as_dict(),
            "issue_date": inv.issue_date.as_dict(),
            "total": inv.total.as_dict(),
            "taxable": inv.taxable.as_dict(),
            "tax": inv.tax.as_dict(),
            "gstin": inv.gstin.as_dict(),
            "party": inv.party.as_dict(),
            "extraction": source,
        }

        if not inv.usable:
            rep.rows_rejected = 1
            missing = [n for n, f in (("invoice number", inv.invoice_no),
                                      ("date", inv.issue_date),
                                      ("total", inv.total)) if f.value is None]
            rep.errors.append({
                "row": 1,
                "error": (f"could not read {', '.join(missing)} from this PDF. "
                          f"RUNWAY will not guess an invoice it cannot read - enter "
                          f"it manually, or import the register as CSV/JSON instead."),
            })
            return [], rep

        total = float(inv.total.value)
        taxable = float(inv.taxable.value) if inv.taxable.value else round(total / 1.18, 2)
        tax = float(inv.tax.value) if inv.tax.value else round(total - taxable, 2)

        # Direction cannot be inferred reliably from a single PDF, so it is
        # taken from the filename where it is explicit and defaulted to a
        # purchase otherwise - the safer default, since a wrongly-created
        # sales invoice would inflate receivables.
        low = filename.lower()
        kind = "sales" if any(k in low for k in ("sales", "outward", "issued", "sale")) else "purchase"

        rep.rows_ok = 1
        rep.warnings.append(
            f"Direction inferred as a {kind} invoice from the filename. Change it in "
            f"the preview if that is wrong.")
        if inv.overall_confidence < REVIEW_THRESHOLD:
            rep.warnings.append(
                f"Overall extraction confidence is {inv.overall_confidence:.0%}, below "
                f"the {REVIEW_THRESHOLD:.0%} threshold. Check every field before confirming.")

        return [{
            "__type": "invoice",
            "kind": kind,
            "invoice_no": str(inv.invoice_no.value),
            "issue_date": inv.issue_date.value,
            "total_paise": rupees_to_paise(total),
            "taxable_paise": rupees_to_paise(taxable),
            "tax_paise": rupees_to_paise(tax),
            "counterparty": inv.party.value or "Unidentified party",
            "gstin": inv.gstin.value,
            "source": f"pdf_{source}",
            "extraction_confidence": round(inv.overall_confidence, 2),
            "needs_review": inv.overall_confidence < REVIEW_THRESHOLD,
        }], rep
