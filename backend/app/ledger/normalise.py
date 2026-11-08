"""Narration normalisation, fingerprinting and duplicate detection."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, timedelta

from app.core.enums import ReconStatus
from app.models import Transaction

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPACE = re.compile(r"\s+")
# Bank narration noise that carries no counterparty signal.
_NOISE = {
    "neft", "rtgs", "imps", "upi", "ach", "nach", "chq", "cheque", "clg", "mmt",
    "inf", "trf", "transfer", "payment", "pymt", "ref", "txn", "dr", "cr",
    "to", "from", "by", "of", "the", "and", "for", "via", "p2a", "p2m", "ib",
    "net", "banking", "fund", "funds", "india", "pvt", "ltd", "limited", "llp",
    "co", "company", "enterprises", "enterprise", "traders", "trading",
}
_LONG_DIGITS = re.compile(r"\b\d{6,}\b")


def normalise_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = _PUNCT.sub(" ", s.lower())
    return _SPACE.sub(" ", s).strip()


def narration_tokens(narration: str) -> list[str]:
    """Content words of a bank narration, with transport noise removed."""
    text = _LONG_DIGITS.sub(" ", normalise_text(narration))
    return [t for t in text.split() if len(t) > 2 and t not in _NOISE]


def party_key(name: str) -> str:
    """Canonical key for entity resolution (ABC Distributors Pvt Ltd -> 'abc distributors')."""
    toks = [t for t in normalise_text(name).split()
            if t not in {"pvt", "ltd", "limited", "llp", "co", "company", "inc", "and", "the"}]
    return " ".join(toks) or normalise_text(name)


def fingerprint(*, business_id: str, account_id: str, value_date: date,
                amount_paise: int, direction: str, reference_no: str | None,
                narration: str) -> str:
    """Stable identity for an imported row.

    A *strong* fingerprint uses the bank's own reference number when present;
    otherwise it falls back to date+amount+normalised narration. The fallback
    is deliberately weaker, which is why a fingerprint collision without a
    reference number raises a *suspected* duplicate rather than dropping the
    row (see ``detect_duplicate``).
    """
    if reference_no:
        core = f"{account_id}|{direction}|{amount_paise}|{reference_no.strip().upper()}"
    else:
        core = (f"{account_id}|{direction}|{amount_paise}|{value_date.isoformat()}"
                f"|{' '.join(narration_tokens(narration)[:6])}")
    return hashlib.sha256(f"{business_id}|{core}".encode()).hexdigest()[:48]


def detect_duplicate(db, business_id: str, candidate: Transaction) -> tuple[bool, str | None, str]:
    """Return ``(is_hard_duplicate, existing_id, reason)``.

    Rules, in order:
      1. Identical fingerprint built from a bank reference number -> hard
         duplicate; the row is rejected.
      2. Identical fingerprint without a reference number -> *suspected*
         duplicate; the row is imported and flagged for the owner.
      3. Same account, same signed amount, within 1 day, highly similar
         narration -> suspected duplicate.

    RUNWAY never silently merges two rows because their amounts match - a
    genuine business can and does pay the same supplier the same amount twice.
    """
    from sqlalchemy import select

    existing = db.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.fingerprint == candidate.fingerprint,
        ).limit(1)
    ).first()
    if existing:
        if candidate.reference_no:
            return True, existing.id, "identical bank reference number, amount and account"
        return False, existing.id, "same date, amount and narration with no bank reference"

    window = [candidate.value_date - timedelta(days=1), candidate.value_date + timedelta(days=1)]
    near = db.scalars(
        select(Transaction).where(
            Transaction.business_id == business_id,
            Transaction.account_id == candidate.account_id,
            Transaction.amount_paise == candidate.amount_paise,
            Transaction.direction == candidate.direction,
            Transaction.value_date >= window[0],
            Transaction.value_date <= window[1],
        ).limit(5)
    ).all()
    ct = set(narration_tokens(candidate.narration))
    for n in near:
        nt = set(narration_tokens(n.narration))
        if ct and nt and len(ct & nt) / max(1, len(ct | nt)) >= 0.75:
            return False, n.id, "same amount within 1 day with near-identical narration"
    return False, None, ""


def mark_suspected_duplicate(txn: Transaction, existing_id: str, reason: str) -> None:
    txn.recon_status = ReconStatus.DUPLICATE_SUSPECT
    txn.duplicate_of = existing_id
    txn.transform_log_json = list(txn.transform_log_json or []) + [
        {"step": "duplicate_check", "result": "suspected", "against": existing_id, "reason": reason}
    ]
