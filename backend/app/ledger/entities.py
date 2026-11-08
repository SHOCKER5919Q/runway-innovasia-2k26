"""Counterparty resolution: turn a bank narration into a known party."""
from __future__ import annotations

from sqlalchemy import select

from app.core.enums import Direction, PartyType
from app.ledger.normalise import narration_tokens, party_key
from app.models import Counterparty

# A match below this is reported as "unidentified counterparty" rather than guessed.
MATCH_THRESHOLD = 0.52


def _score(party: Counterparty, tokens: set[str], raw_norm: str) -> float:
    """Blend of exact-substring and token-overlap evidence."""
    keys = [party.normalised_name] + [party_key(a) for a in (party.aliases_json or [])]
    best = 0.0
    for key in keys:
        if not key:
            continue
        if key in raw_norm:                      # whole canonical name appears verbatim
            best = max(best, 0.97)
            continue
        kt = set(key.split())
        if not kt:
            continue
        overlap = len(kt & tokens)
        if overlap == 0:
            continue
        # Recall over the party's own tokens matters most: a narration rarely
        # repeats the full legal name but almost always carries its head word.
        recall = overlap / len(kt)
        precision = overlap / max(1, len(tokens))
        best = max(best, 0.70 * recall + 0.30 * precision)
    return best


def resolve_counterparty(
    db, business_id: str, narration: str, direction: str,
    *, cache: dict[str, list[Counterparty]] | None = None,
) -> tuple[str | None, float, str]:
    """Return ``(counterparty_id, confidence, rationale)``.

    Direction is used only as a tie-breaker, never as a hard filter: a
    customer can issue a refund and a supplier can send a credit note.
    """
    if cache is not None and business_id in cache:
        parties = cache[business_id]
    else:
        parties = list(db.scalars(select(Counterparty).where(Counterparty.business_id == business_id)).all())
        if cache is not None:
            cache[business_id] = parties
    if not parties:
        return None, 0.0, "no counterparty master data"

    toks = set(narration_tokens(narration))
    raw_norm = " ".join(narration_tokens(narration))
    expected = PartyType.CUSTOMER if direction == Direction.CREDIT else PartyType.SUPPLIER

    scored: list[tuple[float, Counterparty]] = []
    for p in parties:
        s = _score(p, toks, raw_norm)
        if s <= 0:
            continue
        if p.party_type in (expected, PartyType.BOTH):
            s += 0.05                                   # small directional prior
        scored.append((s, p))
    if not scored:
        return None, 0.0, "no name overlap with any known counterparty"
    scored.sort(key=lambda x: x[0], reverse=True)
    top_score, top = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    if top_score < MATCH_THRESHOLD:
        return None, top_score, f"best candidate '{top.name}' scored {top_score:.2f}, below threshold"
    if runner > 0 and (top_score - runner) < 0.08:
        return None, top_score, (f"ambiguous between '{top.name}' and '{scored[1][1].name}' "
                                 f"({top_score:.2f} vs {runner:.2f}) - needs review")
    return top.id, min(0.99, top_score), f"matched '{top.name}' on narration tokens ({top_score:.2f})"
