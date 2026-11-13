"""Load the real UCI Online Retail II statement as its own workspace.

    python -m app.seed.real_uci            # create, or replace, the workspace

The CSV is produced by ``data/real/uci_online_retail_ii/convert.py`` from the
untouched UCI file (see SOURCE.md there). It is imported through
``integrations.service.import_file`` - the same code path as a bank statement
uploaded on the Integrations screen - so this exercises the real pipeline
(parse -> dedupe -> classify -> reconcile -> state rebuild), not a shortcut.

The workspace is attached to the three demo users so it appears in their
business switcher. It is never marked as demo data.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.enums import AccountKind, Industry, Role
from app.digital_twin.digital_twin_service import invalidate
from app.integrations.history import import_with_impact
from app.integrations.service import import_file
from app.models import Account, Business, Membership, User, _uid
from app.seed.seed import DEMO_USERS, wipe_business

ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = ROOT / "data" / "real" / "uci_online_retail_ii" / "bank_statement_inr.csv"
BUSINESS_NAME = "UCI Online Retail II (real data)"
OPENING_DATE = date(2010, 4, 1)
AS_OF = date(2011, 12, 9)          # last day in the dataset


def load(*, replace: bool = True) -> dict:
    if not CSV_PATH.exists():
        raise SystemExit(f"{CSV_PATH} is missing - run data/real/uci_online_retail_ii/convert.py")
    db = SessionLocal()
    try:
        existing = db.scalar(select(Business).where(Business.name == BUSINESS_NAME))
        if existing is not None:
            if not replace:
                return {"business_id": existing.id, "created": False}
            wipe_business(db, existing.id)

        biz = Business(
            id=_uid(), name=BUSINESS_NAME,
            legal_name="Anonymous UK online gift-ware retailer (UCI dataset 502)",
            industry=Industry.RETAIL, city="United Kingdom", is_demo=False,
            demo_scenario=None, msme_class="none", safety_buffer_paise=0,
            settings_json={"data_source": {
                "dataset": "UCI Online Retail II (id 502)",
                "url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
                "licence": "CC BY 4.0",
                "converted_by": "data/real/uci_online_retail_ii/convert.py",
                "as_of_hint": AS_OF.isoformat(),
                "limits": "Sales, refunds and fees only: no suppliers, payroll or "
                          "rent in the source data."}})
        db.add(biz)
        db.flush()
        acct = Account(id=_uid(), business_id=biz.id,
                       name="Current A/c - online sales settlements",
                       kind=AccountKind.CURRENT, bank_name="(not in source data)",
                       currency="INR", opening_balance_paise=0, opening_date=OPENING_DATE,
                       source_system="uci_online_retail_ii")
        db.add(acct)
        for email, _name, role, _pw, _ca in DEMO_USERS:
            u = db.scalar(select(User).where(User.email == email))
            if u is not None:
                db.add(Membership(id=_uid(), user_id=u.id, business_id=biz.id, role=role,
                                  scopes_json=["read:*", "write:*"]
                                  if role != Role.VIEWER else ["read:*"]))
        db.commit()

        result = import_with_impact(db, import_file, business_id=biz.id, as_of=AS_OF,
                                    account_id=acct.id, adapter_key="bank_csv",
                                    content=CSV_PATH.read_bytes(), filename=CSV_PATH.name,
                                    dry_run=False)
        invalidate(biz.id)
        return {"business_id": biz.id, "account_id": acct.id, "created": True,
                "rows_imported": result.get("rows_imported"),
                "duplicates": result.get("duplicates") or result.get("rows_duplicate"),
                "batch_id": result.get("batch_id"), "as_of": AS_OF.isoformat()}
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", action="store_true", help="do nothing if it already exists")
    a = ap.parse_args()
    print(load(replace=not a.keep))


if __name__ == "__main__":
    main()
