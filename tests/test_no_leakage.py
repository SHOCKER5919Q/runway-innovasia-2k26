"""The payment-delay model must never see the future.

These tests exist because a leaky feature pipeline produces an excellent
test score and a worthless live model, and the failure is invisible unless
it is asserted.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from sqlalchemy import select

from app.core.enums import InvoiceKind
from app.forecast.features import FEATURE_NAMES, build_features, settled_rows
from app.forecast.payment_delay import train
from app.models import Invoice

TODAY = date(2026, 11, 7)


def test_feature_vector_matches_the_declared_names(db, business_id):
    invs = db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all()
    rows = build_features(invs, TODAY)
    assert rows
    assert all(len(r.x) == len(FEATURE_NAMES) for r in rows)
    assert all(np.isfinite(r.x).all() for r in rows[:200])


def test_customer_history_features_only_use_earlier_settlements(db, business_id):
    """Recomputing the features with every settlement after a cut-off removed
    must leave the features of earlier invoices byte-identical."""
    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.kind == InvoiceKind.SALES)).all()
    cutoff = TODAY - timedelta(days=200)

    full = {r.invoice_id: r.x.copy() for r in build_features(invs, TODAY)
            if r.issue_date <= cutoff}

    class Masked:
        """A stand-in invoice whose settlement is hidden if it happened after
        the cut-off - i.e. the world as it looked on the cut-off date."""
        __slots__ = ("id", "kind", "invoice_no", "counterparty_id", "issue_date",
                     "due_date", "credit_days", "total_paise", "settled_date",
                     "first_payment_date", "outstanding_paise", "settled_paise",
                     "written_off_paise", "status")

        def __init__(self, src):
            for f in self.__slots__:
                setattr(self, f, getattr(src, f, None))
            if self.settled_date and self.settled_date > cutoff:
                self.settled_date = None
                self.first_payment_date = None
                self.settled_paise = 0
                self.outstanding_paise = self.total_paise

    masked = [Masked(i) for i in invs]
    trimmed = {r.invoice_id: r.x.copy() for r in build_features(masked, cutoff)}

    compared = 0
    for inv_id, x in full.items():
        if inv_id not in trimmed:
            continue
        compared += 1
        assert np.allclose(x, trimmed[inv_id], atol=1e-9), (
            f"invoice {inv_id} features changed when later settlements were hidden - "
            f"the pipeline is leaking future information")
    assert compared > 50, "not enough overlap to make this test meaningful"


def test_training_split_is_chronological(db, business_id):
    invs = db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all()
    m = train(invs, TODAY)
    assert m.metrics["split"] == "chronological (no shuffling)"
    assert m.n_train > 0 and m.n_test > 0


def test_targets_are_only_realised_delays(db, business_id):
    invs = db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all()
    rows = settled_rows(build_features(invs, TODAY))
    by_id = {i.id: i for i in invs}
    for r in rows[:300]:
        inv = by_id[r.invoice_id]
        assert inv.settled_date is not None
        assert r.y == float((inv.settled_date - inv.due_date).days)


def test_an_open_invoice_has_no_target(db, business_id):
    invs = db.scalars(select(Invoice).where(Invoice.business_id == business_id)).all()
    rows = build_features(invs, TODAY)
    for r in rows:
        if r.outstanding_paise > 0 and r.settled_date is None:
            assert r.y is None
