#!/usr/bin/env python3
"""Check that every VARCHAR column is wide enough for what the code writes.

    python scripts/audit_schema.py

**Why this script exists.** SQLite ignores `VARCHAR(n)` length limits
entirely; PostgreSQL enforces them. A column sized against SQLite can
therefore work perfectly for months and then fail the moment the same code
runs on Postgres. That is exactly what happened here:
`predicted_snapshots.model_version` was `String(40)` holding a 41-character
value, and nothing noticed until the first real Postgres run.

Two checks:

1. **Against the live data** — the longest value actually stored in each
   column, which catches anything the application has already written.
2. **Against the code's own vocabulary** — the longest value each column
   *could* hold, derived from the enums, classifier rules, scenario kinds
   and adapter keys. This catches latent overflows that the current data
   happens not to exercise.

Exit code 0 means every column has room.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import String, text  # noqa: E402

from app.core.db import Base, SessionLocal  # noqa: E402
from app import models  # noqa: F401,E402

# Headroom below which a column is reported as tight even though it fits.
TIGHT_RATIO = 0.85

# Columns whose width is a fixed-format contract rather than a guess, so
# "exactly full" is correct and not a warning.
FIXED_WIDTH = {
    32: "uuid4 hex id",
    3: "ISO 4217 currency code",
    15: "GSTIN",
    4: "GST state code",
}


def vocabulary() -> dict[tuple[str, str], tuple[int, str]]:
    """Longest value each column could receive, from the code itself."""
    from app.core.enums import (
        AccountKind, AlertLevel, DecisionStatus, Direction, Evidence,
        IntegrationStatus, Industry, InvoiceKind, InvoiceStatus,
        ObligationKind, PartyType, ReconStatus, Role, ScenarioKind, StateType,
        TxnCategory,
    )
    from app.integrations import REGISTRY
    from app.ledger.classifier import RULES

    def longest(values) -> tuple[int, str]:
        best = max(values, key=len, default="")
        return len(best), best

    v: dict[tuple[str, str], tuple[int, str]] = {}

    def put(table, col, values):
        v[(table, col)] = longest([str(x) for x in values])

    put("transactions", "category", [e.value for e in TxnCategory])
    put("transactions", "category_source", [r.label for r in RULES] + ["owner", "synthetic", "rules"])
    put("transactions", "recon_status", [e.value for e in ReconStatus])
    put("transactions", "evidence", [e.value for e in Evidence])
    put("transactions", "direction", [e.value for e in Direction])
    put("transactions", "source_system", list(REGISTRY) + ["manual", "synthetic", "payment_gateway", "bank_csv"])
    put("invoices", "status", [e.value for e in InvoiceStatus])
    put("invoices", "kind", [e.value for e in InvoiceKind])
    put("invoices", "evidence", [e.value for e in Evidence])
    put("obligations", "kind", [e.value for e in ObligationKind])
    put("obligations", "evidence", [e.value for e in Evidence])
    put("counterparties", "party_type", [e.value for e in PartyType])
    put("accounts", "kind", [e.value for e in AccountKind])
    put("businesses", "industry", [e.value for e in Industry])
    put("memberships", "role", [e.value for e in Role])
    put("alerts", "level", [e.value for e in AlertLevel])
    put("business_states", "state_type", [e.value for e in StateType])
    put("business_states", "trigger", [f"scenario:{k.value}" for k in ScenarioKind]
        + ["manual", "seed", "bundle", "backfill", "manual_refresh", "bootstrap"])
    put("scenarios", "kind", [e.value for e in ScenarioKind])
    put("scenario_decisions", "status", [e.value for e in DecisionStatus])
    put("import_batches", "adapter", list(REGISTRY))
    put("state_comparisons", "comparison_type",
        ["actual_vs_predicted", "predicted_vs_simulated", "simulated_vs_actual"])
    put("copilot_messages", "generator", ["deterministic", "llm",
                                          "deterministic (LLM reply rejected: unverified figures)"])
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    vocab = vocabulary()
    db = SessionLocal()
    overflow: list[str] = []
    tight: list[str] = []
    checked = 0

    try:
        for table in Base.metadata.sorted_tables:
            for col in table.columns:
                if not isinstance(col.type, String):
                    continue
                limit = getattr(col.type, "length", None)
                if not limit:
                    continue
                checked += 1

                # 1. what is actually stored
                try:
                    stored = db.execute(text(
                        f'SELECT MAX(LENGTH("{col.name}")) FROM "{table.name}"')).scalar() or 0
                except Exception:
                    stored = 0

                # 2. what the code could write
                vlen, vexample = vocab.get((table.name, col.name), (0, ""))

                worst = max(stored, vlen)
                src = "data" if stored >= vlen else f"code ({vexample!r})"
                if worst > limit:
                    overflow.append(
                        f"{table.name}.{col.name}: declared {limit}, needs {worst} — from {src}")
                elif limit in FIXED_WIDTH and worst == limit:
                    pass           # exact by contract, not a near miss
                elif limit and worst > limit * TIGHT_RATIO and limit > 8:
                    tight.append(
                        f"{table.name}.{col.name}: declared {limit}, longest {worst} — from {src}")
    finally:
        db.close()

    if not a.quiet:
        print(f"{checked} VARCHAR columns checked against stored data and the code's vocabulary.\n")
        if tight:
            print(f"{len(tight)} column(s) within {int((1-TIGHT_RATIO)*100)}% of their limit "
                  f"(fine, but worth knowing):")
            for t in tight:
                print("  -", t)
            print()

    if overflow:
        print(f"{len(overflow)} OVERFLOW(S) — these will fail on PostgreSQL:")
        for o in overflow:
            print("  -", o)
        return 1

    print("Every VARCHAR column has room for what the code can write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
