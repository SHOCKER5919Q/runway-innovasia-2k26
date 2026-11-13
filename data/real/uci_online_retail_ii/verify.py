"""Check RUNWAY's numbers for the real UCI workspace against an independent
calculation done straight from the CSV with pandas.

    backend/.venv/bin/python data/real/uci_online_retail_ii/verify.py \
        [--api http://127.0.0.1:8000] [--as-of 2011-12-09]

Each check prints the expected value, what the API returned, and PASS/FAIL.
The expected side never imports RUNWAY code, so a bug in the engine cannot
make its own test pass.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CSV = Path(__file__).resolve().parent / "bank_statement_inr.csv"
BUSINESS = "UCI Online Retail II (real data)"


def api(base, path, token=None, biz=None, body=None):
    h = {"content-type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if biz:
        h["X-Business-Id"] = biz
    req = urllib.request.Request(base + path, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--as-of", default="2011-12-09")
    a = ap.parse_args()
    as_of = date.fromisoformat(a.as_of)
    q = f"?as_of={a.as_of}"

    # ── expected, from the CSV alone ─────────────────────────────────────
    df = pd.read_csv(CSV, parse_dates=["Date"])
    df = df[df.Date.dt.date <= as_of]
    dep = df["Deposit (INR)"].fillna(0)
    wd = df["Withdrawal (INR)"].fillna(0)
    exp = {}
    exp["rows"] = len(df)
    exp["cash_paise"] = round((dep.sum() - wd.sum()) * 100)
    start = pd.Timestamp(as_of - timedelta(days=29))
    w = df[df.Date >= start]
    exp["inflow_30d_paise"] = round(w["Deposit (INR)"].fillna(0).sum() * 100)
    exp["outflow_30d_paise"] = round(w["Withdrawal (INR)"].fillna(0).sum() * 100)
    sales = df[df.Narration.str.startswith("Online sales")]
    exp["sales_rows"] = len(sales)

    # ── actual, from the running API ─────────────────────────────────────
    tok = api(a.api, "/api/auth/login", body={"email": "owner@runway.demo",
                                               "password": "demo1234"})
    token = tok.get("access_token") or tok.get("token")
    biz = next(b["id"] for b in tok["businesses"] if b["name"] == BUSINESS)
    ov = api(a.api, "/api/overview" + q, token, biz)
    tx = api(a.api, "/api/transactions" + q + "&limit=1", token, biz)
    got = {
        "cash_paise": ov["headline"]["cash_in_hand"]["paise"],
        "inflow_30d_paise": ov["flow_30d"]["inflow_paise"],
        "outflow_30d_paise": ov["flow_30d"]["outflow_paise"],
        "rows": tx.get("total") or tx.get("count") or ov["data_quality"]["transactions"],
    }

    checks = [("transactions imported", exp["rows"], got["rows"], 0),
              ("cash in hand (paise)", exp["cash_paise"], got["cash_paise"], 1),
              ("30-day inflow (paise)", exp["inflow_30d_paise"], got["inflow_30d_paise"], 1),
              ("30-day outflow (paise)", exp["outflow_30d_paise"], got["outflow_30d_paise"], 1)]
    bad = 0
    print(f"{'check':28} {'expected':>20} {'RUNWAY':>20}  result")
    for name, e, g, tol in checks:
        ok = g is not None and abs(int(e) - int(g)) <= tol
        bad += not ok
        print(f"{name:28} {int(e):>20,} {int(g or 0):>20,}  {'PASS' if ok else 'FAIL'}")

    f = ov["forecast"]
    print("\nforecast (predicted, for inspection):")
    print("  opening cash         ", f"{f['p50'][0]/100:,.0f}")
    print("  P50 at week 13       ", f"{f['p50'][-1]/100:,.0f}")
    print("  P10 / P90 at week 13 ", f"{f['p10'][-1]/100:,.0f} / {f['p90'][-1]/100:,.0f}")
    print("  breach probability   ", ov["headline"]["breach_probability"])
    print("  health               ", ov["headline"]["health_score"], ov["headline"]["health_band"])
    print("  data quality         ", ov["data_quality"]["score"], ov["data_quality"]["warnings"])
    print(f"\n{len(checks) - bad}/{len(checks)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
