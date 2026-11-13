"""Who must approve a new member before they can see a business.

    owner       created the business - no approval needed
    manager     the owner must approve
    accountant  a manager AND the owner must both approve
    viewer      the owner must approve

Until every required approval is recorded the membership stays ``pending``
and ``deps.get_tenant`` refuses it, so a pending user cannot read a single
figure from the business. One rejection by any required approver ends the
request.

Exception, stated rather than hidden: if the business has no approved
manager, nobody could ever give the manager half of an accountant's approval
and the request would wait forever. In that case the owner's approval is
enough, and the approval record says so.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.enums import MembershipStatus, Role

REQUIRED: dict[str, tuple[str, ...]] = {
    Role.OWNER: (),
    Role.MANAGER: (Role.OWNER,),
    Role.ACCOUNTANT: (Role.MANAGER, Role.OWNER),
    Role.VIEWER: (Role.OWNER,),
}

# Characters that cannot be misread when a code is read out over the phone.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_join_code() -> str:
    return "RW-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def ensure_join_code(db, business) -> str:
    if not business.join_code:
        from app.models import Business
        while True:
            code = new_join_code()
            if not db.scalar(select(Business).where(Business.join_code == code)):
                business.join_code = code
                break
    return business.join_code


def has_approved_manager(db, business_id: str) -> bool:
    from app.models import Membership
    return db.scalar(select(Membership).where(
        Membership.business_id == business_id, Membership.role == Role.MANAGER,
        Membership.status == MembershipStatus.APPROVED)) is not None


def required_for(db, membership) -> list[str]:
    req = list(REQUIRED.get(membership.role, (Role.OWNER,)))
    if Role.MANAGER in req and not has_approved_manager(db, membership.business_id):
        req.remove(Role.MANAGER)
    return req


def outstanding(db, membership) -> list[str]:
    done = {a["role"] for a in (membership.approvals_json or [])
            if a.get("decision") == "approved"}
    return [r for r in required_for(db, membership) if r not in done]


def can_decide(db, membership, approver_role: str) -> bool:
    return (membership.status == MembershipStatus.PENDING
            and approver_role in outstanding(db, membership))


def decide(db, membership, *, approver, approver_role: str, approve: bool,
           note: str | None = None) -> dict:
    """Record one approver's decision and settle the membership's status."""
    if not can_decide(db, membership, approver_role):
        raise PermissionError(
            "Your approval is not needed for this request, or it was already decided.")
    entry = {"role": approver_role, "user_id": approver.id, "name": approver.full_name,
             "decision": "approved" if approve else "rejected",
             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if note:
        entry["note"] = note[:300]
    if approver_role == Role.OWNER and Role.MANAGER in REQUIRED.get(membership.role, ()) \
            and not has_approved_manager(db, membership.business_id):
        entry["covers"] = "manager (this business has no approved manager)"
    membership.approvals_json = list(membership.approvals_json or []) + [entry]
    if not approve:
        membership.status = MembershipStatus.REJECTED
    elif not outstanding(db, membership):
        membership.status = MembershipStatus.APPROVED
    return {"status": membership.status, "waiting_for": outstanding(db, membership)
            if membership.status == MembershipStatus.PENDING else []}
