"""Concrete importers that work today, with no credentials."""
from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any

from app.core.enums import Direction, Evidence, IntegrationStatus
from app.core.money import rupees_to_paise
from app.integrations.base import Adapter, NormalisedRow, ParseReport, register

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y",
                "%m/%d/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d-%b-%y", "%Y%m%d"]


def parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None


def parse_money(s: Any) -> float | None:
    if s is None:
        return None
    t = str(s).strip().replace(",", "").replace("₹", "").replace("INR", "").strip()
    if not t or t in {"-", "--", "NA", "N/A"}:
        return None
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    t = re.sub(r"\s*(Dr|Cr|DR|CR)\.?$", "", t).strip()
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


_INWARD_FILE = re.compile(r"gstr[-_ ]?2[ab]\b|gstr[-_ ]?2[ab][-_.]|\binward|purchase")
_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]")

# Synonyms seen across Indian bank statement exports.
COLUMNS = {
    "date": ["date", "txndate", "transactiondate", "valuedate", "vdate", "dateoftransaction",
             "paymentdate", "paiddate", "settlementdate", "valuedt", "txndt"],
    "posting_date": ["postingdate", "bookingdate", "postdate"],
    "narration": ["narration", "description", "particulars", "details", "remarks",
                  "transactionremarks", "transactiondetails", "purpose", "notes", "memo"],
    "reference": ["chqrefno", "refno", "referenceno", "reference", "ref", "chequeno", "utr", "utrno",
                  "transactionid", "txnid", "referencenumber", "chqnoref", "paymentid"],
    "debit": ["debit", "withdrawal", "withdrawalamt", "withdrawalamount", "dr",
              "debitamount", "paymentsdebit"],
    "credit": ["credit", "deposit", "depositamt", "depositamount", "cr",
               "creditamount", "receiptscredit"],
    "amount": ["amount", "transactionamount", "amt", "value", "paymentamountinr",
               "paymentamount", "amountinr", "txnamount", "netamount", "grossamount"],
    "type": ["type", "drcr", "crdr", "transactiontype", "indicator"],
    "balance": ["balance", "closingbalance", "runningbalance", "balanceamt"],
}


# Exports often tag amount columns with a currency: "Withdrawal (INR)",
# "Deposit Amt (Rs.)". A rupee tag is stripped so the column still matches;
# a foreign-currency column is ignored, because picking "Deposit (GBP)" over
# "Deposit (INR)" would silently import the wrong amounts.
_RUPEE_TAGS = ("inr", "rs", "rupees")
_FOREIGN_TAGS = ("usd", "gbp", "eur", "aed", "sgd", "jpy", "cny", "fx")


def _variants(h: str) -> list[str]:
    n = _norm(h)
    for t in _FOREIGN_TAGS:
        if n.endswith(t) and len(n) > len(t):
            return []
    out = [n]
    for t in _RUPEE_TAGS:
        if n.endswith(t) and len(n) > len(t):
            out.append(n[: -len(t)])
    return out


def map_columns(headers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    norm: dict[str, str] = {}
    for h in headers:
        for v in _variants(h):
            norm.setdefault(v, h)
    for field, names in COLUMNS.items():
        for n in names:
            if n in norm:
                out[field] = norm[n]
                break
    return out


def xlsx_to_csv(content: bytes) -> bytes:
    """First worksheet of an .xlsx file as CSV bytes.

    Bank portals offer "Download as Excel" as often as CSV. Dates are written
    as ISO strings and numbers without thousands separators, so the CSV
    parser downstream reads them exactly as it reads a CSV export.
    """
    import datetime as _dt
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for row in ws.iter_rows(values_only=True):
        if row is None or all(v is None for v in row):
            continue
        w.writerow(["" if v is None
                    else v.date().isoformat() if isinstance(v, _dt.datetime)
                    else v.isoformat() if isinstance(v, _dt.date)
                    else repr(v) if isinstance(v, float) and v != int(v)
                    else str(int(v)) if isinstance(v, float)
                    else str(v) for v in row])
    wb.close()
    return buf.getvalue().encode("utf-8")


def _is_xlsx(content: bytes, filename: str) -> bool:
    return filename.lower().endswith((".xlsx", ".xlsm")) or content[:4] == b"PK\x03\x04"


@register
class BankStatementCSV(Adapter):
    key = "bank_csv"
    label = "Bank statement (CSV / Excel export)"
    category = "bank"
    status = IntegrationStatus.AVAILABLE
    description = ("Imports a bank statement exported from net banking. Column names "
                   "are detected automatically across the common Indian bank formats, "
                   "and separate debit/credit columns or a single signed amount both work.")
    requirements = ["A CSV or Excel (.xlsx) export from your bank. No credentials are stored."]
    accepts = [".csv", ".txt", ".xlsx"]

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[NormalisedRow], ParseReport]:
        rep = ParseReport(detected_format="bank_csv")
        if _is_xlsx(content, filename):
            rep.detected_format = "bank_xlsx"
            try:
                content = xlsx_to_csv(content)
            except Exception as e:  # corrupt or password-protected workbook
                rep.errors.append({"row": 0, "error": f"could not read the Excel file: {e}"})
                return [], rep
        text = content.decode("utf-8-sig", errors="replace")
        # Some bank exports carry preamble lines before the real header.
        lines = text.splitlines()
        start = 0
        for i, ln in enumerate(lines[:25]):
            if sum(1 for f in ("date", "narration", "description", "particulars",
                               "withdrawal", "deposit", "debit", "credit",
                               "amount", "payment", "reference")
                   if f in ln.lower()) >= 2:
                start = i
                break
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        headers = reader.fieldnames or []
        norm_map = {_norm(h): h for h in headers}
        cmap = map_columns(headers)

        def pick_extra(*names):
            for n in names:
                if n in norm_map:
                    return norm_map[n]
            return None

        c_party = pick_extra("customername", "customer", "partyname", "party",
                             "counterparty", "suppliername", "supplier",
                             "vendorname", "vendor")
        c_inv = pick_extra("invoiceid", "invoiceno", "invoicenumber", "billno", "billid")
        c_mode = pick_extra("paymentmode", "mode", "channel", "paymentmethod")
        c_payid = pick_extra("paymentid", "receiptid")
        for key, col in (("party", c_party), ("invoice_ref", c_inv), ("mode", c_mode)):
            if col and key not in cmap:
                cmap[key] = col
        rep.column_mapping = cmap

        if "date" not in cmap:
            if ({"invoicedate", "issuedate", "duedate", "invoiceamountinr"} & set(norm_map)) and "paymentdate" not in norm_map:
                rep.errors.append({
                    "row": 0,
                    "error": ("This looks like an invoices CSV (found Invoice_Date / Invoice_Amount columns), "
                              "not a bank or payments sheet. Switch Source to 'Invoices & supplier bills (CSV)'."),
                    "headers": headers,
                })
                return [], rep
            rep.errors.append({"row": 0, "error": "no recognisable date column",
                               "headers": headers})
            return [], rep
        if not ({"debit", "credit"} & set(cmap)) and "amount" not in cmap:
            if "invoiceamountinr" in norm_map or "outstandinginr" in norm_map:
                rep.errors.append({
                    "row": 0,
                    "error": ("This looks like an invoices CSV (found Invoice_Amount_INR / Outstanding_INR), "
                              "not a bank or payments sheet. Switch Source to 'Invoices & supplier bills (CSV)'."),
                    "headers": headers,
                })
                return [], rep
            rep.errors.append({"row": 0, "error": "no amount, debit or credit column",
                               "headers": headers})
            return [], rep

        default_is_debit = bool(c_party and _norm(c_party).startswith(("supplier", "vendor")))
        rows: list[NormalisedRow] = []
        for n, raw in enumerate(reader, start=1):
            rep.rows_seen += 1
            d = parse_date(raw.get(cmap["date"], ""))
            if d is None:
                rep.rows_rejected += 1
                rep.errors.append({"row": n, "error": "unparseable date",
                                   "value": raw.get(cmap["date"])})
                continue
            dr = parse_money(raw.get(cmap.get("debit", ""), "")) or 0.0
            cr = parse_money(raw.get(cmap.get("credit", ""), "")) or 0.0
            if dr == 0 and cr == 0 and "amount" in cmap:
                amt = parse_money(raw.get(cmap["amount"], ""))
                if amt is None:
                    rep.rows_rejected += 1
                    rep.errors.append({"row": n, "error": "unparseable amount"})
                    continue
                flag = (raw.get(cmap.get("type", ""), "") or "").strip().upper()
                if flag.startswith("D") or (not flag and (amt < 0 or (amt > 0 and default_is_debit))):
                    dr = abs(amt)
                else:
                    cr = abs(amt)
            if dr == 0 and cr == 0:
                rep.rows_rejected += 1
                rep.errors.append({"row": n, "error": "zero amount"})
                continue
            direction = Direction.DEBIT if dr > 0 else Direction.CREDIT
            amount = rupees_to_paise(dr if dr > 0 else cr)
            party = (raw.get(c_party, "") or "").strip() if c_party else ""
            inv_ref = (raw.get(c_inv, "") or "").strip() if c_inv else ""
            mode = (raw.get(c_mode, "") or "").strip() if c_mode else ""
            pay_id = (raw.get(c_payid, "") or "").strip() if c_payid else ""
            narr = (raw.get(cmap.get("narration", ""), "") or "").strip()
            if not narr:
                prep = ("from" if direction == Direction.CREDIT else "to") if party else ""
                narr = " ".join(p for p in [
                    mode or ("Receipt" if direction == Direction.CREDIT else "Payment"),
                    prep,
                    party,
                    f"against {inv_ref}" if inv_ref else "",
                    pay_id,
                ] if p).strip()
            rows.append(NormalisedRow(
                value_date=d,
                posting_date=parse_date(raw.get(cmap.get("posting_date", ""), "")) or d,
                amount_paise=amount, direction=direction,
                narration=narr,
                reference_no=(raw.get(cmap.get("reference", ""), "") or "").strip() or (pay_id or None),
                counterparty_hint=party or None,
                invoice_ref=inv_ref or None,
                raw=dict(raw)))
            rep.rows_ok += 1
        if rep.rows_rejected:
            rep.warnings.append(f"{rep.rows_rejected} rows could not be read and were "
                                f"skipped. They are listed in the import report so "
                                f"nothing disappears silently.")
        return rows, rep


@register
class UPISettlementCSV(Adapter):
    key = "upi_settlement_csv"
    label = "UPI / payment gateway settlement file"
    category = "payments"
    status = IntegrationStatus.AVAILABLE
    description = ("Imports a settlement report with gross, fee and net columns. RUNWAY "
                   "credits the invoice with the gross and books the fee as a separate "
                   "expense, so receivables actually clear instead of being left short "
                   "by the MDR.")
    requirements = ["A settlement report exported from your gateway dashboard."]

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[NormalisedRow], ParseReport]:
        rep = ParseReport(detected_format="gateway_settlement")
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
        headers = reader.fieldnames or []
        norm = {_norm(h): h for h in headers}

        def pick(*names):
            for n in names:
                if n in norm:
                    return norm[n]
            return None

        c_date = pick("settlementdate", "date", "settledon", "txndate", "paymentdate", "paiddate")
        c_gross = pick("grossamount", "gross", "amount", "orderamount",
                       "paymentamountinr", "paymentamount", "amountinr")
        c_fee = pick("fee", "feeamount", "mdr", "commission", "charges")
        c_net = pick("netamount", "net", "settlementamount", "amountsettled")
        c_ref = pick("settlementid", "utr", "referenceid", "reference", "paymentid", "transactionid")
        c_note = pick("description", "notes", "narration", "invoicenumber", "invoiceid", "invoiceno", "orderid")
        c_party = pick("customername", "customer", "partyname", "party", "counterparty")
        c_inv = pick("invoiceid", "invoiceno", "invoicenumber", "orderid")
        rep.column_mapping = {k: v for k, v in {
            "date": c_date, "gross": c_gross, "fee": c_fee,
            "net": c_net, "ref": c_ref, "party": c_party, "invoice_ref": c_inv,
        }.items() if v}
        if not c_date or not (c_gross or c_net):
            rep.errors.append({"row": 0, "error": "settlement file needs a date and a "
                                                  "gross or net amount column",
                               "headers": headers})
            return [], rep

        rows: list[NormalisedRow] = []
        for n, raw in enumerate(reader, start=1):
            rep.rows_seen += 1
            d = parse_date(raw.get(c_date, ""))
            gross = parse_money(raw.get(c_gross, "")) if c_gross else None
            net = parse_money(raw.get(c_net, "")) if c_net else None
            fee = parse_money(raw.get(c_fee, "")) if c_fee else None
            if d is None or (gross is None and net is None):
                rep.rows_rejected += 1
                rep.errors.append({"row": n, "error": "missing date or amount"})
                continue
            if gross is None:
                gross = (net or 0) + (fee or 0)
            if net is None:
                net = gross - (fee or 0)
            if fee is None:
                fee = gross - net
            ref = (raw.get(c_ref, "") or "").strip() or None
            note = (raw.get(c_note, "") or "").strip()
            party = (raw.get(c_party, "") or "").strip() if c_party else ""
            inv_ref = (raw.get(c_inv, "") or "").strip() if c_inv else (note or "")
            narr = " ".join(p for p in ["SETTLEMENT", ref or "", party, inv_ref if inv_ref != note else "", note] if p).strip()
            rows.append(NormalisedRow(
                value_date=d, amount_paise=rupees_to_paise(net),
                direction=Direction.CREDIT,
                narration=narr,
                reference_no=ref, counterparty_hint=party or None,
                gross_paise=rupees_to_paise(gross),
                fee_paise=rupees_to_paise(fee), invoice_ref=inv_ref or None,
                raw=dict(raw)))
            rep.rows_ok += 1
        rep.warnings.append("The gateway fee is recorded separately; the invoice is "
                            "credited with the gross so it settles in full.")
        return rows, rep


@register
class TallyXML(Adapter):
    key = "tally_xml"
    label = "TallyPrime XML export (daybook / vouchers)"
    category = "accounting"
    status = IntegrationStatus.AVAILABLE
    description = ("Imports a Tally voucher XML export. Receipt and payment vouchers "
                   "become transactions; sales and purchase vouchers become invoices.")
    requirements = ["Gateway of Tally > Display > Day Book > Export > XML"]
    accepts = [".xml"]
    produces = "transactions+invoices"

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[dict], ParseReport]:
        rep = ParseReport(detected_format="tally_xml")
        out: list[dict] = []
        try:
            root = ET.fromstring(content.decode("utf-8", errors="replace"))
        except ET.ParseError as e:
            rep.errors.append({"row": 0, "error": f"invalid XML: {e}"})
            return [], rep

        for v in root.iter():
            if not v.tag.upper().endswith("VOUCHER"):
                continue
            rep.rows_seen += 1
            def txt(tag):
                el = v.find(tag)
                if el is None:
                    for c in v.iter():
                        if c.tag.upper() == tag.upper():
                            el = c
                            break
                return (el.text or "").strip() if el is not None and el.text else ""

            vtype = (v.get("VCHTYPE") or txt("VOUCHERTYPENAME")).strip()
            d = parse_date(txt("DATE"))
            party = txt("PARTYLEDGERNAME") or txt("PARTYNAME")
            vno = txt("VOUCHERNUMBER")
            narr = txt("NARRATION")
            amount = None
            for le in v.iter():
                if le.tag.upper() == "AMOUNT" and le.text:
                    a = parse_money(le.text)
                    if a is not None and (amount is None or abs(a) > abs(amount)):
                        amount = a
            if d is None or amount is None:
                rep.rows_rejected += 1
                rep.errors.append({"row": rep.rows_seen,
                                   "error": "voucher missing a date or an amount",
                                   "voucher": vno})
                continue
            kind = vtype.lower()
            if "sales" in kind or "purchase" in kind:
                out.append({"__type": "invoice", "kind": "sales" if "sales" in kind else "purchase",
                            "invoice_no": vno or f"TALLY-{rep.rows_seen}",
                            "issue_date": d, "total_paise": rupees_to_paise(abs(amount)),
                            "counterparty": party, "narration": narr,
                            "voucher_type": vtype})
            else:
                direction = Direction.CREDIT if ("receipt" in kind or amount > 0) else Direction.DEBIT
                out.append({"__type": "transaction",
                            "row": NormalisedRow(
                                value_date=d, amount_paise=rupees_to_paise(abs(amount)),
                                direction=direction,
                                narration=f"{vtype} {vno} {party} {narr}".strip(),
                                reference_no=vno or None, counterparty_hint=party or None,
                                evidence=Evidence.IMPORTED_ACTUAL,
                                raw={"voucher_type": vtype, "party": party})})
            rep.rows_ok += 1
        return out, rep


@register
class GSTInvoiceJSON(Adapter):
    key = "gst_invoice_json"
    label = "GST invoice register (JSON or CSV)"
    category = "compliance"
    status = IntegrationStatus.AVAILABLE
    description = ("Imports a GSTR-1 style outward-supply register or a GSTR-2B style "
                   "inward register as invoices, including taxable value and tax.")
    requirements = ["A JSON or CSV export of the invoice register."]
    accepts = [".json", ".csv"]
    produces = "invoices"

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[dict], ParseReport]:
        rep = ParseReport(detected_format="gst_register")
        text = content.decode("utf-8-sig", errors="replace")
        records: list[dict] = []
        if text.lstrip().startswith(("{", "[")):
            try:
                doc = json.loads(text)
            except json.JSONDecodeError as e:
                rep.errors.append({"row": 0, "error": f"invalid JSON: {e}"})
                return [], rep
            if isinstance(doc, dict):
                for key in ("b2b", "invoices", "docs", "data"):
                    if key in doc:
                        doc = doc[key]
                        break
            if isinstance(doc, dict):
                doc = [doc]
            for entry in doc:
                if isinstance(entry, dict) and "inv" in entry:
                    for inv in entry["inv"]:
                        records.append({**inv, "ctin": entry.get("ctin"),
                                        "cfs": entry.get("cfs")})
                else:
                    records.append(entry)
        else:
            records = list(csv.DictReader(io.StringIO(text)))

        out: list[dict] = []
        for n, r in enumerate(records, start=1):
            rep.rows_seen += 1
            low = {_norm(k): v for k, v in r.items()}
            no = (low.get("inum") or low.get("invoiceno") or low.get("invoicenumber")
                  or low.get("documentnumber") or "")
            d = parse_date(str(low.get("idt") or low.get("invoicedate")
                               or low.get("date") or ""))
            val = parse_money(low.get("val") or low.get("invoicevalue")
                              or low.get("total") or low.get("totalamount"))
            txval = parse_money(low.get("txval") or low.get("taxablevalue"))
            tax = sum(x for x in (parse_money(low.get(k)) or 0
                                  for k in ("iamt", "camt", "samt", "igst", "cgst", "sgst",
                                            "taxamount")) if x)
            party = (low.get("ctin") or low.get("gstin") or low.get("partyname")
                     or low.get("customername") or low.get("suppliername") or "")
            if not no or d is None or (val is None and txval is None):
                rep.rows_rejected += 1
                rep.errors.append({"row": n, "error": "invoice needs a number, a date "
                                                      "and a value"})
                continue
            if val is None:
                val = (txval or 0) + tax
            if txval is None:
                txval = val - tax
            # GSTR-2A/2B and "inward" registers are purchases. A plain "2b"
            # test also matched GSTR-1 "b2b" files and booked sales as
            # purchases.
            kind = ("purchase" if (_INWARD_FILE.search(filename.lower())
                                   or low.get("suppliername")) else "sales")
            out.append({"__type": "invoice", "kind": kind, "invoice_no": str(no),
                        "issue_date": d, "total_paise": rupees_to_paise(val),
                        "taxable_paise": rupees_to_paise(txval),
                        "tax_paise": rupees_to_paise(tax),
                        "counterparty": str(party),
                        # Only a real GSTIN goes in the GSTIN field; a party
                        # name used to be truncated into it.
                        "gstin": (str(party).upper() if _GSTIN.fullmatch(str(party).upper())
                                  else None),
                        "source": "gst_register"})
            rep.rows_ok += 1
        rep.warnings.append("Invoice direction is inferred from the file name and the "
                            "columns present. Check the preview before confirming.")
        return out, rep


@register
class InvoicesCSV(Adapter):
    key = "invoices_csv"
    label = "Invoices & supplier bills (CSV)"
    category = "invoices"
    status = IntegrationStatus.AVAILABLE
    description = ("Imports open and past customer invoices and supplier bills from a "
                   "simple CSV spreadsheet, including due dates, paid amounts, settlement "
                   "dates and supplier MSME status.")
    requirements = ["A CSV spreadsheet of sales invoices and/or supplier bills."]
    accepts = [".csv", ".txt"]
    produces = "invoices"

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[dict], ParseReport]:
        rep = ParseReport(detected_format="invoices_csv")
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        norm = {_norm(h): h for h in headers}

        def pick(*names):
            for n in names:
                if n in norm:
                    return norm[n]
            return None

        c_kind = pick("kind", "type", "invoicetype", "doctype")
        c_no = pick("invoiceno", "invoicenumber", "invoiceid", "billno", "billid", "number", "docno", "inum")
        c_party = pick("party", "partyname", "counterparty", "customer", "customername",
                       "supplier", "suppliername", "vendor", "vendorname", "name")
        c_issue = pick("issuedate", "date", "invoicedate", "billdate", "idt")
        c_due = pick("duedate", "paymentdue", "dueon", "due")
        c_credit = pick("creditdays", "terms", "paymentterms")
        c_total = pick("total", "totalamount", "amount", "invoicevalue", "invoiceamount",
                       "invoiceamountinr", "totalinr", "amountinr", "billamount", "billamountinr",
                       "val", "value")
        c_tax = pick("tax", "taxamount", "gst", "gstamount")
        c_paid = pick("paid", "paidamount", "amountpaid", "amountpaidinr", "paidamountinr",
                      "settled", "settledamount", "received", "receivedamount")
        c_outstanding = pick("outstanding", "outstandinginr", "outstandingamount",
                             "balance", "balancedue", "dueamount", "unpaid")
        c_sdate = pick("settleddate", "paiddate", "paymentdate")
        c_purpose = pick("purpose", "description", "narration", "notes", "remarks", "item", "particulars")
        c_msme = pick("msme", "msmeclass", "udyammicrosmall")
        c_gstin = pick("gstin", "ctin")
        rep.column_mapping = {
            k: v for k, v in {
                "kind": c_kind, "invoice_no": c_no, "party": c_party,
                "issue_date": c_issue, "due_date": c_due, "total": c_total,
                "paid": c_paid or c_outstanding, "settled_date": c_sdate, "msme_class": c_msme,
            }.items() if v
        }
        if not c_no or not c_issue or not c_total or not c_party:
            if ({"paymentid", "paymentdate", "paymentamountinr"} & set(norm)) and not c_issue:
                rep.errors.append({
                    "row": 0,
                    "error": ("This looks like a customer payments / transactions CSV (found Payment_Date / "
                              "Payment_Amount_INR), not an invoices sheet. Switch Source to "
                              "'Bank statement (CSV / Excel export)'."),
                    "headers": headers,
                })
                return [], rep
            rep.errors.append({"row": 0,
                               "error": "CSV needs party, invoice_no, issue_date, and total columns",
                               "headers": headers})
            return [], rep

        default_kind = "purchase" if c_party and _norm(c_party).startswith(("supplier", "vendor")) else "sales"
        out: list[dict] = []
        for n, raw in enumerate(reader, start=1):
            rep.rows_seen += 1
            no = (raw.get(c_no, "") or "").strip()
            party = (raw.get(c_party, "") or "").strip()
            issue = parse_date(raw.get(c_issue, ""))
            total = parse_money(raw.get(c_total, ""))
            if not no or not party or issue is None or total is None or total <= 0:
                rep.rows_rejected += 1
                rep.errors.append({"row": n, "error": "missing or invalid party, invoice_no, issue_date, or total"})
                continue
            raw_kind = (raw.get(c_kind, "") if c_kind else "").strip().lower()
            if raw_kind:
                kind = "purchase" if raw_kind in {"purchase", "payable", "bill", "supplier", "vendor", "ap"} else "sales"
            else:
                kind = default_kind
            due = parse_date(raw.get(c_due, "")) if c_due else None
            credit_days = 30
            if c_credit and (raw.get(c_credit, "") or "").strip():
                try:
                    credit_days = max(0, int(float(raw[c_credit])))
                except ValueError:
                    credit_days = 30
            elif due is not None:
                credit_days = max(0, (due - issue).days)
            total_paise = rupees_to_paise(total)
            tax_val = parse_money(raw.get(c_tax, "")) if c_tax else None
            tax_paise = rupees_to_paise(tax_val) if tax_val is not None else None
            paid_val = parse_money(raw.get(c_paid, "")) if c_paid else None
            if paid_val is None and c_outstanding:
                out_val = parse_money(raw.get(c_outstanding, ""))
                if out_val is not None:
                    paid_val = max(0.0, total - out_val)
            settled_paise = min(total_paise, max(0, rupees_to_paise(paid_val or 0.0)))
            settled_date = parse_date(raw.get(c_sdate, "")) if c_sdate else None
            if settled_paise >= total_paise and settled_date is None:
                settled_date = due or issue
            msme_raw = (raw.get(c_msme, "") if c_msme else "").strip().lower()
            msme_class = msme_raw if msme_raw in {"micro", "small", "medium", "none"} else None
            gstin = (raw.get(c_gstin, "") if c_gstin else "").strip().upper()[:15] or None
            purpose = (raw.get(c_purpose, "") if c_purpose else "").strip() or None

            out.append({
                "__type": "invoice",
                "kind": kind,
                "invoice_no": no,
                "counterparty": party,
                "issue_date": issue,
                "due_date": due,
                "credit_days": credit_days,
                "total_paise": total_paise,
                "tax_paise": tax_paise,
                "taxable_paise": (total_paise - tax_paise) if tax_paise is not None else None,
                "settled_paise": settled_paise,
                "settled_date": settled_date,
                "msme_class": msme_class,
                "gstin": gstin,
                "narration": purpose,
                "source": "invoices_csv",
            })
            rep.rows_ok += 1
        return out, rep


@register
class ManualEntry(Adapter):
    key = "manual"
    label = "Manual entry"
    category = "manual"
    status = IntegrationStatus.AVAILABLE
    description = "Type in a transaction, invoice or obligation directly."
    requirements = []
    accepts = []

    def parse(self, content: bytes, *, filename: str = ""):
        return [], ParseReport(detected_format="manual")


@register
class AASamplePayload(Adapter):
    key = "aa_sample"
    label = "Account Aggregator sample payload (ReBIT shape)"
    category = "banking"
    status = IntegrationStatus.SANDBOX_REQUIRED
    description = ("Parses a ReBIT-shaped deposit FI payload. This exercises the real "
                   "ingestion path against sample data. RUNWAY is NOT connected to any "
                   "Account Aggregator and claims no live AA connectivity: that needs "
                   "an eligible FIU arrangement.")
    requirements = ["An FIU arrangement with a licensed NBFC-AA for live data.",
                    "Sample or sandbox payloads work today for testing."]
    accepts = [".json", ".xml"]

    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[NormalisedRow], ParseReport]:
        rep = ParseReport(detected_format="aa_deposit_fi")
        text = content.decode("utf-8", errors="replace")
        rows: list[NormalisedRow] = []
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as e:
            rep.errors.append({"row": 0, "error": f"invalid JSON: {e}"})
            return [], rep

        def walk(node):
            if isinstance(node, dict):
                if {"type", "amount"} <= set(k.lower() for k in node):
                    yield node
                for v in node.values():
                    yield from walk(v)
            elif isinstance(node, list):
                for v in node:
                    yield from walk(v)

        for n, t in enumerate(walk(doc), start=1):
            rep.rows_seen += 1
            low = {k.lower(): v for k, v in t.items()}
            d = parse_date(str(low.get("valuedate") or low.get("transactiontimestamp")
                               or low.get("date") or "")[:10])
            amt = parse_money(low.get("amount"))
            if d is None or amt is None:
                rep.rows_rejected += 1
                continue
            rows.append(NormalisedRow(
                value_date=d, amount_paise=rupees_to_paise(abs(amt)),
                direction=(Direction.CREDIT if str(low.get("type", "")).upper().startswith("CREDIT")
                           else Direction.DEBIT),
                narration=str(low.get("narration") or low.get("remarks") or ""),
                reference_no=str(low.get("txnid") or low.get("reference") or "") or None,
                evidence=Evidence.IMPORTED_ACTUAL, raw=dict(t)))
            rep.rows_ok += 1
        rep.warnings.append("Parsed from a sample payload. No live Account Aggregator "
                            "connection is configured or implied.")
        return rows, rep
