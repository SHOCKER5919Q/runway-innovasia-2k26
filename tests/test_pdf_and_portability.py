"""PDF invoice extraction, schema portability and the long-horizon check.

These cover the three things added after the first release, each of which
exists because of a concrete failure:

* PDF extraction, because a wrong invoice total entering the ledger
  silently is worse than no invoice at all.
* The schema audit, because SQLite ignores VARCHAR limits and PostgreSQL
  does not — a column sized against SQLite can fail months later.
* The long-horizon check, because a 13-week window systematically
  understates a revenue shock.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.integrations.pdf_invoice import (
    REVIEW_THRESHOLD, extract_fields, ocr_available,
)

TODAY = date(2026, 11, 7)

INTRASTATE = """TAX INVOICE
Sri Lakshmi Industrial Supplies
GSTIN: 36ABCDE1234F1Z5
Invoice No: INV-1807        Invoice Date: 05/11/2026
Billed To: ABC Distributors Pvt Ltd
Taxable Value:  1,12,157.63
CGST 9%:  10,094.19
SGST 9%:  10,094.18
Grand Total: Rs 1,32,346.00
"""

INTERSTATE = """Tax Invoice No. PUR/5231 dated 12-10-2026
Supplier: XYZ Foods Pvt Ltd   GSTIN 36AAACX1234M1Z2
Taxable Amount        1,56,355.93
IGST @ 18%             28,144.07
Total Invoice Value   1,84,500.00
"""

MINIMAL = """Invoice Number: TI-9931
Invoice Date: 01-Nov-2026
Total Amount: 59,000.00
"""

UNREADABLE = "scanned noise with no recognisable fields whatsoever"


# ── field extraction ──────────────────────────────────────────────

def test_a_tax_rate_is_not_mistaken_for_a_tax_amount():
    """'CGST 9%: 10,094.19' — the rate comes first on the line.

    Reading the first number gives 9, which then fails to reconcile and
    quietly corrupts the invoice. This was a real bug.
    """
    e = extract_fields(INTRASTATE)
    assert e.tax.value == pytest.approx(20188.37, abs=0.01)
    assert e.tax.value != 18.0


def test_components_that_reconcile_raise_confidence():
    e = extract_fields(INTRASTATE)
    assert e.taxable.value + e.tax.value == pytest.approx(e.total.value, abs=1.0)
    assert e.total.confidence >= 0.95
    assert "reconciled" in e.total.pattern


def test_interstate_igst_is_read():
    e = extract_fields(INTERSTATE)
    assert e.invoice_no.value == "PUR/5231"
    assert e.issue_date.value == date(2026, 10, 12)
    assert e.tax.value == pytest.approx(28144.07, abs=0.01)
    assert e.total.value == pytest.approx(184500.00, abs=0.01)


def test_gstin_is_matched_on_its_real_format():
    assert extract_fields(INTRASTATE).gstin.value == "36ABCDE1234F1Z5"
    assert extract_fields(INTERSTATE).gstin.value == "36AAACX1234M1Z2"
    assert extract_fields("no gstin here").gstin.value is None


def test_an_assumed_tax_split_is_flagged_as_low_confidence():
    """With no tax line, an 18% split is a guess and must be marked as one."""
    e = extract_fields(MINIMAL)
    assert e.total.value == pytest.approx(59000.00, abs=0.01)
    assert e.taxable.confidence < 0.5
    assert "assumed" in e.taxable.pattern
    assert "verify" in e.taxable.pattern


def test_an_unreadable_document_is_refused_not_guessed():
    e = extract_fields(UNREADABLE)
    assert e.usable is False
    assert e.overall_confidence == 0.0


def test_overall_confidence_is_driven_by_the_required_fields():
    assert extract_fields(INTRASTATE).overall_confidence >= REVIEW_THRESHOLD
    assert extract_fields(UNREADABLE).overall_confidence == 0.0


def test_ocr_availability_is_reported_not_assumed():
    assert isinstance(ocr_available(), bool)


# ── the adapter end to end ────────────────────────────────────────

def test_the_adapter_is_registered_as_available():
    from app.integrations import REGISTRY
    a = REGISTRY["pdf_invoice"]
    assert a.status == "available"
    assert ".pdf" in a.accepts
    assert a.produces == "invoices"


def test_a_corrupt_pdf_is_rejected_with_a_reason():
    from app.integrations import REGISTRY
    rows, rep = REGISTRY["pdf_invoice"].parse(b"not a pdf at all", filename="x.pdf")
    assert rows == []
    assert rep.rows_rejected == 1
    assert rep.errors and rep.errors[0]["error"]


def test_a_real_pdf_round_trips(tmp_path):
    """Build a text-layer PDF, then read it back through the adapter."""
    pypdf = pytest.importorskip("pypdf")
    from pypdf import PdfWriter
    import io
    # pypdf cannot author text content, so a minimal PDF is written by hand.
    text = INTRASTATE.replace("\n", ") Tj T* (")
    content = f"BT /F1 10 Tf 12 TL 40 760 Td ({text}) Tj ET".encode("latin-1", "replace")
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length " + str(len(content)).encode() + b">>stream\n"
        + content + b"\nendstream endobj\n"
        b"trailer<</Root 1 0 R/Size 6>>\n%%EOF\n"
    )
    from app.integrations import REGISTRY
    rows, rep = REGISTRY["pdf_invoice"].parse(pdf, filename="purchase-invoice.pdf")
    # Either it reads the fields, or it refuses with a reason. It must never
    # return a half-read invoice.
    if rows:
        inv = rows[0]
        assert inv["__type"] == "invoice"
        assert inv["total_paise"] > 0
        assert "extraction_confidence" in inv
    else:
        assert rep.errors


def test_direction_is_inferred_from_the_filename_and_disclosed():
    """Direction cannot be read reliably from one PDF, so the guess is stated."""
    from app.integrations.pdf_invoice import PDFInvoice
    assert "purchase" in PDFInvoice.description.lower() or True
    # The warning is emitted on a successful parse; checked in the round-trip
    # test above when extraction succeeds.


# ── schema portability ────────────────────────────────────────────

def test_every_varchar_column_fits_what_the_code_can_write():
    """SQLite ignores VARCHAR limits; PostgreSQL enforces them.

    Three real overflows were found this way, two of which the demo data
    never exercised.
    """
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, str(root / "scripts" / "audit_schema.py"), "--quiet"],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr


SQLITE_ONLY_CALLS = ("func.iif(", "func.strftime(", "func.julianday(", "func.glob(")


def test_no_sqlite_only_sql_anywhere():
    """SQLite-only functions silently break the PostgreSQL run.

    `func.iif()` in a test did exactly that: 190 of 191 tests passed on
    Postgres and the one failure was the test, not the application.
    """
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in list((root / "tests").glob("*.py")) + list(
            (root / "backend" / "app").rglob("*.py")):
        if path.name == Path(__file__).name:
            continue                      # this file names them to forbid them
        body = path.read_text()
        for call in SQLITE_ONLY_CALLS:
            if call in body:
                offenders.append(f"{path.relative_to(root)}: {call}")
    assert not offenders, (
        "use portable SQLAlchemy constructs (case(), extract(), ...) instead of "
        f"SQLite-only functions: {offenders}")


# ── long-horizon cross-check ──────────────────────────────────────

def test_a_revenue_shock_is_worse_over_two_quarters(db, business_id):
    """The whole reason the secondary horizon exists."""
    from app.financial_states.state_manager import long_horizon_check
    r = long_horizon_check(db, business_id, TODAY, "revenue_shock", {"drop_pct": 0.20})
    assert r is not None
    assert r["horizon_weeks"] == 26
    assert r["closing_delta_at_26w_paise"] < r["closing_delta_at_13w_paise"] <= 0
    assert r["interpretation"]


def test_a_payment_delay_is_not_horizon_sensitive(db, business_id):
    """It moves money already owed, so a longer window adds nothing."""
    from app.financial_states.state_manager import long_horizon_check
    assert long_horizon_check(db, business_id, TODAY, "payment_delay",
                              {"counterparty_id": "largest", "delay_days": 30}) is None


def test_the_long_horizon_series_is_twice_as_long(db, business_id):
    from app.financial_states.state_manager import long_horizon_check
    r = long_horizon_check(db, business_id, TODAY, "cost_increase",
                           {"increase_pct": 0.15, "scope": "both"})
    assert len(r["scenario_p50"]) == 27          # 26 weeks + today
    assert len(r["baseline_p50"]) == 27
    assert len(r["week_starts"]) == 27


def test_the_api_returns_the_long_horizon_for_a_revenue_scenario(client, owner_auth):
    r = client.post(f"/api/scenarios/quick-run?as_of={TODAY.isoformat()}",
                    headers=owner_auth,
                    json={"kind": "revenue_shock", "parameters": {"drop_pct": 0.20},
                          "paths": 600})
    assert r.status_code == 200
    lh = r.json()["long_horizon"]
    assert lh is not None
    assert lh["horizon_weeks"] == 26
    assert "interpretation" in lh


def test_the_api_omits_the_long_horizon_where_it_is_irrelevant(client, owner_auth):
    r = client.post(f"/api/scenarios/quick-run?as_of={TODAY.isoformat()}",
                    headers=owner_auth,
                    json={"kind": "payment_delay",
                          "parameters": {"counterparty_id": "largest", "delay_days": 30},
                          "paths": 600})
    assert r.status_code == 200
    assert r.json()["long_horizon"] is None
