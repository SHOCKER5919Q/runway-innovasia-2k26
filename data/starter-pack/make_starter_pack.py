"""Three files that bring a brand-new RUNWAY workspace fully to life.

    backend/.venv/bin/python data/starter-pack/make_starter_pack.py

Upload them in this order on Integrations (as-of date 2026-11-07):
  1. 1-sales-register.csv     -> adapter "GST invoice register"  (customers + receivables)
  2. 2-purchase-register.csv  -> adapter "GST invoice register"  (suppliers + payables)
  3. 3-bank-statement.csv     -> adapter "Bank statement"         (cash; settles invoices)

26 weeks of history (May-Nov 2026): enough for every model (see
docs/DATA_HISTORY_REQUIREMENTS.md). SYNTHETIC demo data for a fictional
textile trader - deterministic (fixed seed), not real transactions.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
START, AS_OF = date(2026, 5, 4), date(2026, 11, 7)
rng = random.Random(20261107)

# name, credit days, typical delay (days late), invoice size (Rs), invoices per month
CUSTOMERS = [
    ("Sharma Garments", 30, 4, 180000, 4),
    ("Lakshmi Fabrics", 45, 18, 260000, 3),
    ("Kaveri Textiles", 30, 0, 95000, 5),
    ("Mehta Fashion House", 60, 32, 340000, 2),
    ("Deccan Uniforms", 30, 9, 140000, 3),
    ("Sai Boutique Chain", 30, 2, 70000, 4),
]
SUPPLIERS = [
    ("Surat Yarn Mills", 30, 220000, 3),
    ("Bhilwara Dyeing Works", 45, 150000, 2),
    ("Ludhiana Threads", 30, 60000, 3),
    ("Coimbatore Cotton Co", 60, 300000, 1),
]


def d(x: date) -> str:
    return x.strftime("%d/%m/%Y")


def main() -> None:
    sales, buys, bank = [], [], []
    n = 2001
    for name, cdays, delay, size, per_month in CUSTOMERS:
        day = START + timedelta(days=rng.randint(0, 6))
        while day <= AS_OF:
            amt = round(size * rng.uniform(0.7, 1.3), -2)
            tax = round(amt * 0.05, 2)                       # 5% GST on fabric
            no = f"INV-{n}"; n += 1
            sales.append((no, day, name, amt, tax))
            paid = day + timedelta(days=cdays + max(-3, int(rng.gauss(delay, 6))))
            if paid <= AS_OF:
                bank.append((paid, f"NEFT CR-{name.upper()}-{no}", f"N{no[4:]}C", 0, amt + tax))
            day += timedelta(days=int(30 / per_month) + rng.randint(-2, 3))
    p = 7001
    for name, cdays, size, per_month in SUPPLIERS:
        day = START + timedelta(days=rng.randint(0, 6))
        while day <= AS_OF:
            amt = round(size * rng.uniform(0.8, 1.2), -2)
            tax = round(amt * 0.05, 2)
            no = f"PUR-{p}"; p += 1
            buys.append((no, day, name, amt, tax))
            paid = day + timedelta(days=cdays + rng.randint(-2, 6))
            if paid <= AS_OF:
                bank.append((paid, f"NEFT DR-{name.upper()}-{no}", f"N{no[4:]}D", amt + tax, 0))
            day += timedelta(days=int(30 / per_month) + rng.randint(-2, 3))

    bank.append((START - timedelta(days=3), "CAPITAL INTRODUCED BY PROPRIETOR", "CAP001", 0, 1500000))
    m = date(2026, 5, 1)
    while m <= AS_OF:
        if m.replace(day=1) >= START.replace(day=1):
            bank.append((m.replace(day=1), "SALARY PAYMENT STAFF BATCH", f"SAL{m:%y%m}", 185000, 0))
            bank.append((m.replace(day=5), "RENT PAYMENT GODOWN SECUNDERABAD", f"RNT{m:%y%m}", 65000, 0))
            bank.append((m.replace(day=12), "TSSPDCL ELECTRICITY BILL", f"EB{m:%y%m}", rng.randint(14000, 22000), 0))
            bank.append((m.replace(day=20), f"GST CHALLAN PMT-06 GSTR-3B {m:%b %Y}".upper(), f"GST{m:%y%m}", rng.randint(38000, 61000), 0))
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    bank = [r for r in bank if r[0] <= AS_OF]
    bank.sort(key=lambda r: (r[0], r[1]))

    (HERE / "1-sales-register.csv").write_text(
        "Invoice No,Invoice Date,Customer Name,Taxable Value,IGST,Invoice Value\n" +
        "".join(f"{no},{d(dt)},{c},{a:.2f},{t:.2f},{a + t:.2f}\n" for no, dt, c, a, t in sales))
    (HERE / "2-purchase-register.csv").write_text(
        "Invoice No,Invoice Date,Supplier Name,Taxable Value,IGST,Invoice Value\n" +
        "".join(f"{no},{d(dt)},{s},{a:.2f},{t:.2f},{a + t:.2f}\n" for no, dt, s, a, t in buys))
    (HERE / "3-bank-statement.csv").write_text(
        "Date,Narration,Chq./Ref.No.,Withdrawal Amt.,Deposit Amt.\n" +
        "".join(f"{d(dt)},{nar},{ref},{dr:.2f}" if dr else f"{d(dt)},{nar},{ref},"
                for dt, nar, ref, dr, cr in []) +
        "".join(f"{d(dt)},{nar},{ref},{(f'{dr:.2f}' if dr else '')},{(f'{cr:.2f}' if cr else '')}\n"
                for dt, nar, ref, dr, cr in bank))
    print(f"sales invoices {len(sales)}, purchase bills {len(buys)}, bank rows {len(bank)}")


if __name__ == "__main__":
    main()
