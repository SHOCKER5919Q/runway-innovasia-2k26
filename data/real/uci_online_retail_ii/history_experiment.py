"""How much history does the sales forecast need? Measured on real data.

    cd backend && .venv/bin/python ../data/real/uci_online_retail_ii/history_experiment.py

For each Monday from 4 Apr to 7 Nov 2011, RUNWAY's own run-rate estimator
(forecast.cashflow.revenue_runrate) forecasts the next 4 weeks of sales using
only the last H weeks of the real UCI ledger. The forecast is compared with
the receipts that actually arrived in those 4 weeks. Read-only.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.enums import Direction, TxnCategory  # noqa: E402
from app.forecast.cashflow import revenue_runrate  # noqa: E402
from app.models import Business, Transaction  # noqa: E402

HISTORY_WEEKS = [4, 6, 8, 13, 26, 52]
HORIZON = 4


def main() -> None:
    db = SessionLocal()
    biz = db.scalar(select(Business).where(Business.name.like("UCI Online Retail II%")))
    if biz is None:
        raise SystemExit("load the real workspace first: ./run.sh seed-real")
    rcpt = db.scalars(select(Transaction).where(
        Transaction.business_id == biz.id, Transaction.direction == Direction.CREDIT,
        Transaction.category == TxnCategory.CUSTOMER_RECEIPT)).all()
    by_day: dict[date, int] = {}
    for t in rcpt:
        by_day[t.value_date] = by_day.get(t.value_date, 0) + t.amount_paise

    def actual(start: date) -> int:
        return sum(v for d, v in by_day.items() if start <= d < start + timedelta(weeks=HORIZON))

    as_ofs, d = [], date(2011, 4, 4)
    while d <= date(2011, 11, 7):
        as_ofs.append(d)
        d += timedelta(weeks=1)

    out = {}
    for h in HISTORY_WEEKS:
        errs = []
        for a in as_ofs:
            fc, meta = revenue_runrate(db, biz.id, a, HORIZON + 1, biz.industry,
                                       lookback_weeks=h)
            pred = sum(fc[:HORIZON])
            act = actual(a + timedelta(days=1))
            if act > 0 and pred > 0:
                errs.append(abs(pred - act) / act)
        out[h] = {"forecasts": len(errs),
                  "mape_pct": round(100 * st.fmean(errs), 1),
                  "median_ape_pct": round(100 * st.median(errs), 1),
                  "p90_ape_pct": round(100 * sorted(errs)[int(0.9 * (len(errs) - 1))], 1)}
    db.rollback()
    db.close()
    print(f"{'history':>8} {'forecasts':>9} {'mean error':>11} {'median':>8} {'90th pct':>9}")
    for h, r in out.items():
        print(f"{h:>5} wk {r['forecasts']:>9} {r['mape_pct']:>10}% {r['median_ape_pct']:>7}% "
              f"{r['p90_ape_pct']:>8}%")
    (Path(__file__).resolve().parent / "history_experiment.json").write_text(
        json.dumps({"as_of_range": [as_ofs[0].isoformat(), as_ofs[-1].isoformat()],
                    "horizon_weeks": HORIZON, "results": out}, indent=2) + "\n")


if __name__ == "__main__":
    main()
