#!/usr/bin/env python3
"""Standalone accounting-invariant checker.

    python scripts/verify_ledger.py [--date YYYY-MM-DD]

Runs the same invariants as the test suite directly against the live
database, so the books can be audited without running pytest.
Exit code 0 means every invariant holds.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.analytics.cash import account_balance  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.money import format_inr  # noqa: E402
from app.models import Account, Allocation, Business, Invoice, Transaction  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    as_of = date.fromisoformat(a.date) if a.date else date.today()
    db = SessionLocal()
    failures: list[str] = []
    checks = 0
    try:
        for biz in db.scalars(select(Business)).all():
            print(f"\n{biz.name}")
            for acct in db.scalars(select(Account).where(Account.business_id == biz.id)).all():
                b = account_balance(db, acct, as_of)
                checks += 1
                ok = b.closing_paise == b.opening_paise + b.credits_paise - b.debits_paise
                flag = "ok " if ok else "FAIL"
                if not ok:
                    failures.append(f"{biz.name}/{acct.name}: balance identity broken")
                print(f"  [{flag}] {acct.name:<42} opening {format_inr(b.opening_paise):>14} "
                      f"+ {format_inr(b.credits_paise):>14} - {format_inr(b.debits_paise):>14} "
                      f"= {format_inr(b.closing_paise):>14}")

            rows = db.execute(
                select(Allocation.invoice_id, func.sum(Allocation.amount_paise))
                .where(Allocation.business_id == biz.id)
                .group_by(Allocation.invoice_id)).all()
            over = 0
            for inv_id, alloc in rows:
                checks += 1
                inv = db.get(Invoice, inv_id)
                if alloc > inv.total_paise:
                    over += 1
                    failures.append(f"{biz.name}/{inv.invoice_no}: over-allocated")
                if alloc != inv.settled_paise:
                    failures.append(f"{biz.name}/{inv.invoice_no}: settled != allocations")
            print(f"  [{'ok ' if not over else 'FAIL'}] {len(rows)} invoices: "
                  f"allocations never exceed the invoice total")

            trows = db.execute(
                select(Allocation.transaction_id, func.sum(Allocation.amount_paise))
                .where(Allocation.business_id == biz.id)
                .group_by(Allocation.transaction_id)).all()
            bad = 0
            for tid, alloc in trows:
                checks += 1
                t = db.get(Transaction, tid)
                if alloc > t.settleable_paise:
                    bad += 1
                    failures.append(f"{biz.name}/txn {tid}: over-allocated")
            print(f"  [{'ok ' if not bad else 'FAIL'}] {len(trows)} transactions: "
                  f"allocations never exceed the settleable amount")

            neg = db.scalar(select(func.count()).select_from(Invoice).where(
                Invoice.business_id == biz.id,
                Invoice.settled_paise > Invoice.total_paise)) or 0
            checks += 1
            if neg:
                failures.append(f"{biz.name}: {neg} invoices settled beyond their total")
            print(f"  [{'ok ' if not neg else 'FAIL'}] no invoice is settled beyond its total")
    finally:
        db.close()

    print(f"\n{checks} invariant checks run.")
    if failures:
        print(f"{len(failures)} FAILURES:")
        for f in failures[:40]:
            print("  -", f)
        return 1
    print("All accounting invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
