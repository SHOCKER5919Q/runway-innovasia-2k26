"""Money handling.

RUNWAY stores every monetary amount as an **integer number of paise**
(1 rupee = 100 paise).  Floating point is never used for a balance, an
invoice amount or a ledger allocation, which is what makes the accounting
invariants in ``tests/test_ledger_invariants.py`` hold exactly.

Floats appear only inside statistical models (forecasts, Monte Carlo), and
every value that crosses back into the ledger is rounded to paise here.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

PAISE = 100


def rupees_to_paise(value: float | int | str | Decimal) -> int:
    """Convert a rupee amount to integer paise with banker-safe rounding."""
    d = Decimal(str(value)) * PAISE
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> float:
    return round(paise / PAISE, 2)


def to_paise(value: float) -> int:
    """Round a model-produced float (already in paise) to a whole paise."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_inr(paise: int, *, compact: bool = False) -> str:
    """Format paise using the Indian digit grouping (lakh / crore)."""
    sign = "-" if paise < 0 else ""
    rupees = abs(paise) // PAISE
    if compact:
        if rupees >= 1_00_00_000:
            return f"{sign}₹{rupees / 1_00_00_000:.2f} Cr"
        if rupees >= 1_00_000:
            return f"{sign}₹{rupees / 1_00_000:.2f} L"
        if rupees >= 1_000:
            return f"{sign}₹{rupees / 1_000:.1f} K"
        return f"{sign}₹{rupees}"
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return f"{sign}₹{s}"


def split_proportionally(total: int, weights: list[float]) -> list[int]:
    """Split an integer paise amount by weights with no paise lost.

    Uses the largest-remainder method so ``sum(result) == total`` exactly.
    """
    if not weights:
        return []
    swt = sum(weights)
    if swt <= 0:
        base = [total // len(weights)] * len(weights)
        base[0] += total - sum(base)
        return base
    raw = [total * w / swt for w in weights]
    floors = [int(x // 1) for x in raw]
    remainder = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in range(remainder):
        floors[order[i % len(order)]] += 1
    return floors
