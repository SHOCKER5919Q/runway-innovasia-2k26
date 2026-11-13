"""Convert UCI Online Retail II into a RUNWAY bank-statement CSV.

Reproducible: same input file -> byte-identical output. Run from repo root:

    backend/.venv/bin/python data/real/uci_online_retail_ii/download.py
    backend/.venv/bin/python data/real/uci_online_retail_ii/convert.py

Every rule below is documented in SOURCE.md. Nothing is invented: each output
row is an exact sum of real invoice lines for one calendar day, converted to
rupees at the RBI-published financial-year average rate for that day.
"""
from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW_ZIP = HERE / "raw" / "online_retail_ii.zip"
OUT_CSV = HERE / "bank_statement_inr.csv"
OUT_REPORT = HERE / "conversion_report.json"
EXPECTED_SHA256 = "572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb"

WINDOW_START = pd.Timestamp("2010-04-01")      # first day of FY 2010-11
WINDOW_END = pd.Timestamp("2011-12-10")        # exclusive; data ends 2011-12-09

# RBI Handbook of Statistics on the Indian Economy, Table 147: exchange rate
# of the rupee vis-a-vis pound sterling, financial-year annual average
# (FEDAI indicative rates for these years).
INR_PER_GBP = {"2010-11": 70.88, "2011-12": 76.39}

# Lines that are costs the shop paid, not sales or customer refunds.
FEE_CODES = {"AMAZONFEE": "Amazon marketplace fee",
             "BANK CHARGES": "Bank charges",
             "CRUK": "CRUK charity commission"}


def fy(d: pd.Timestamp) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load() -> pd.DataFrame:
    got = sha256(RAW_ZIP)
    if got != EXPECTED_SHA256:
        raise SystemExit(f"raw file hash {got} does not match {EXPECTED_SHA256}")
    with zipfile.ZipFile(RAW_ZIP) as z, z.open("online_retail_II.xlsx") as f:
        sheets = pd.read_excel(f, sheet_name=None,
                               dtype={"Invoice": str, "StockCode": str})
    return pd.concat(sheets.values(), ignore_index=True)


def main() -> None:
    raw = load()
    rep: dict = {"raw_rows": int(len(raw))}
    df = raw.drop_duplicates()
    rep["exact_duplicates_removed"] = int(len(raw) - len(df))
    df = df[(df.InvoiceDate >= WINDOW_START) & (df.InvoiceDate < WINDOW_END)].copy()
    rep["rows_in_window"] = int(len(df))
    df["kind"] = df.Invoice.str[0].where(~df.Invoice.str[0].str.isdigit(), "N")
    rep["bad_debt_adjustment_rows_dropped"] = int((df.kind == "A").sum())
    df = df[df.kind != "A"]
    df["gbp"] = df.Quantity * df.Price
    rep["zero_value_rows_dropped"] = int((df.gbp == 0).sum())
    df = df[df.gbp != 0]
    df["day"] = df.InvoiceDate.dt.normalize()
    df["is_fee"] = df.StockCode.isin(FEE_CODES)

    rows = []
    for day, g in df.groupby("day", sort=True):
        rate = INR_PER_GBP[fy(day)]
        sales = g[(g.kind == "N") & ~g.is_fee]
        refunds = g[(g.kind == "C") & ~g.is_fee]
        fees = g[g.is_fee]
        d = day.date().isoformat()
        if len(sales):
            gbp = round(float(sales.gbp.sum()), 2)
            rows.append((d, f"Online sales settlement - {sales.Invoice.nunique()} orders",
                         f"SALES-{day:%Y%m%d}", 0.0, gbp, rate))
        if len(refunds):
            gbp = round(float(-refunds.gbp.sum()), 2)
            rows.append((d, f"Customer refunds - {refunds.Invoice.nunique()} cancelled orders",
                         f"REFUND-{day:%Y%m%d}", gbp, 0.0, rate))
        for code, label in FEE_CODES.items():
            f_ = fees[fees.StockCode == code]
            if not len(f_):
                continue
            net = round(float(f_.gbp.sum()), 2)
            # Negative on a cancellation invoice = the shop paid the fee.
            if net < 0:
                rows.append((d, f"{label}", f"FEE-{code[:4]}-{day:%Y%m%d}", -net, 0.0, rate))
            elif net > 0:
                rows.append((d, f"{label} - reversal", f"FEE-{code[:4]}-{day:%Y%m%d}",
                             0.0, net, rate))

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["Date", "Narration", "Reference", "Withdrawal (INR)", "Deposit (INR)",
                    "Withdrawal (GBP)", "Deposit (GBP)", "INR per GBP"])
        for d, narr, ref, dr, cr, rate in rows:
            w.writerow([d, narr, ref,
                        f"{dr * rate:.2f}" if dr else "", f"{cr * rate:.2f}" if cr else "",
                        f"{dr:.2f}" if dr else "", f"{cr:.2f}" if cr else "", rate])

    out = pd.read_csv(OUT_CSV)
    dep, wd = out["Deposit (INR)"].fillna(0), out["Withdrawal (INR)"].fillna(0)
    rep.update({
        "window": [WINDOW_START.date().isoformat(), (WINDOW_END.date()).isoformat()],
        "output_rows": int(len(out)),
        "days_with_activity": int(out.Date.nunique()),
        "first_date": out.Date.min(), "last_date": out.Date.max(),
        "total_deposits_inr": round(float(dep.sum()), 2),
        "total_withdrawals_inr": round(float(wd.sum()), 2),
        "net_inr": round(float(dep.sum() - wd.sum()), 2),
        "total_deposits_gbp": round(float(out["Deposit (GBP)"].fillna(0).sum()), 2),
        "total_withdrawals_gbp": round(float(out["Withdrawal (GBP)"].fillna(0).sum()), 2),
        "invoices": {"sales": int(df[(df.kind == "N")].Invoice.nunique()),
                     "cancellations": int(df[(df.kind == "C")].Invoice.nunique())},
        "inr_per_gbp": INR_PER_GBP,
        "raw_sha256": EXPECTED_SHA256,
        "output_sha256": sha256(OUT_CSV),
    })
    OUT_REPORT.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
