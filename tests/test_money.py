"""Money arithmetic must be exact. Everything downstream depends on it."""
from __future__ import annotations

import pytest

from app.core.money import (
    format_inr, paise_to_rupees, rupees_to_paise, split_proportionally, to_paise,
)


@pytest.mark.parametrize("rupees,paise", [
    (0, 0), (1, 100), (0.01, 1), (0.005, 1), (1234.56, 123456),
    (8_24_000, 8_24_000_00), (-150.25, -15025),
])
def test_rupees_to_paise_is_exact(rupees, paise):
    assert rupees_to_paise(rupees) == paise


def test_float_accumulation_does_not_drift():
    """The classic failure: 0.1 + 0.2 != 0.3 in float. In paise it is exact."""
    total = sum(rupees_to_paise("0.1") for _ in range(1000))
    assert total == 100_00
    assert paise_to_rupees(total) == 100.0


@pytest.mark.parametrize("paise,expected", [
    (8_24_000_00, "₹8,24,000"),
    (1_23_45_678_00, "₹1,23,45,678"),
    (999_00, "₹999"),
    (-5_00_000_00, "-₹5,00,000"),
])
def test_indian_digit_grouping(paise, expected):
    assert format_inr(paise) == expected


def test_compact_uses_lakh_and_crore():
    assert format_inr(18_70_000_00, compact=True) == "₹18.70 L"
    assert format_inr(4_80_00_000_00, compact=True) == "₹4.80 Cr"


@pytest.mark.parametrize("total,weights", [
    (1000, [1, 1, 1]), (100, [0.3, 0.3, 0.4]), (7, [5, 3, 1]),
    (1_00_00_001, [0.26, 0.18, 0.11, 0.14, 0.09, 0.07, 0.05, 0.04, 0.04, 0.02]),
])
def test_proportional_split_loses_no_paise(total, weights):
    parts = split_proportionally(total, weights)
    assert sum(parts) == total
    assert len(parts) == len(weights)
    assert all(p >= 0 for p in parts)
