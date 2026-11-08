#!/usr/bin/env python3
"""Regenerate docs/DATA_DICTIONARY.md from the ORM models.

    python scripts/gen_data_dictionary.py

Reads `Base.metadata`, **not** a live database. The models are the source of
truth; a database created before the last change would otherwise produce a
document that quietly disagrees with the code — and on SQLite, which ignores
VARCHAR limits, that disagreement is invisible until it reaches PostgreSQL.

The hand-written preamble, per-table notes and trailing sections of the
existing document are preserved; only the column tables are regenerated.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import Base  # noqa: E402
from app import models  # noqa: F401,E402

DOC = ROOT / "docs" / "DATA_DICTIONARY.md"

GROUPS = [
    ("Tenancy and access", ["businesses", "users", "memberships", "consents", "audit_log"]),
    ("Ledger", ["accounts", "counterparties", "transactions", "invoices", "allocations",
                "obligations", "loans", "import_batches"]),
    ("Three-state architecture", ["business_states", "actual_snapshots",
                                  "predicted_snapshots", "simulated_snapshots",
                                  "state_comparisons", "forecast_points",
                                  "payment_predictions", "model_runs"]),
    ("Decisions and intelligence", ["scenarios", "scenario_decisions", "alerts",
                                    "recommendations", "copilot_messages", "twin_events",
                                    "shared_reports"]),
]


def main() -> int:
    old = DOC.read_text()
    head = old.split("## Tenancy and access")[0]
    tail_marker = "## Relationships that matter"
    tail = tail_marker + old.split(tail_marker)[1]

    # Preserve the hand-written one-line note under each table heading.
    notes = {m.group(1): m.group(2)
             for m in re.finditer(r"^### `(\w+)`\n\n([^|\n][^\n]*)\n", old, re.M)}

    tables = {t.name: t for t in Base.metadata.sorted_tables}
    out = [head.rstrip("\n"), ""]
    seen = set()

    for group, names in GROUPS:
        out.append(f"## {group}\n")
        for name in names:
            t = tables.get(name)
            if t is None:
                continue
            seen.add(name)
            out.append(f"### `{name}`\n")
            if name in notes:
                out.append(notes[name] + "\n")
            out.append("| Column | Type | Null | Default | Notes |")
            out.append("|---|---|---|---|---|")
            for col in t.columns:
                note = []
                if col.primary_key:
                    note.append("**PK**")
                for fk in col.foreign_keys:
                    note.append(f"→ `{fk.column.table.name}`")
                if col.name.endswith("_paise"):
                    note.append("integer paise")
                if col.name == "evidence":
                    note.append("evidence hierarchy")
                default = ""
                d = col.default
                if d is not None and getattr(d, "is_scalar", False):
                    default = f"`{d.arg}`"
                out.append(f"| `{col.name}` | {col.type} | "
                           f"{'yes' if col.nullable else 'no'} | {default} | "
                           f"{' · '.join(note)} |")
            idx = [i for i in t.indexes if i.name]
            if idx:
                out.append("")
                out.append("Indexes: " + ", ".join(
                    f"`{i.name}` ({', '.join(c.name for c in i.columns)})"
                    for i in sorted(idx, key=lambda i: i.name)))
            out.append("")

    missing = set(tables) - seen
    if missing:
        out.append("## Other\n")
        out += [f"- `{n}`" for n in sorted(missing)] + [""]

    out.append("---\n")
    out.append(tail.rstrip("\n") + "\n")
    DOC.write_text("\n".join(out))
    print(f"Wrote {DOC.relative_to(ROOT)} from {len(seen)} model definitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
