"""Team: who belongs to this business, and the approval queue.

The owner sees every request and the join code. A manager sees the requests
a manager is needed for (accountants). Approval rules live in
``app.core.approvals`` so they are stated once.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import jsonable
from app.api.deps import DbDep, Tenant, audit
from app.core import approvals
from app.core.enums import MembershipStatus, Role
from app.models import Membership, User

router = APIRouter(prefix="/api/team", tags=["team"])


def _member_json(db, m: Membership, viewer_role: str) -> dict:
    u = db.get(User, m.user_id)
    return {
        "membership_id": m.id, "user_id": m.user_id,
        "name": u.full_name if u else None, "email": u.email if u else None,
        "role": m.role, "status": m.status,
        "requested_at": m.created_at.isoformat() if m.created_at else None,
        "approvals": m.approvals_json or [],
        "required": approvals.required_for(db, m),
        "waiting_for": approvals.outstanding(db, m)
        if m.status == MembershipStatus.PENDING else [],
        "you_can_decide": approvals.can_decide(db, m, viewer_role),
    }


@router.get("")
def team(db: DbDep, ctx: Tenant):
    ctx.require(Role.MANAGER)
    rows = db.scalars(select(Membership).where(
        Membership.business_id == ctx.business_id)).all()
    members = [_member_json(db, m, ctx.role) for m in rows]
    out = {
        "your_role": ctx.role,
        "members": [m for m in members if m["status"] == MembershipStatus.APPROVED],
        "requests": [m for m in members if m["status"] == MembershipStatus.PENDING],
        "rejected": [m for m in members if m["status"] == MembershipStatus.REJECTED],
        "rules": {"manager": "Owner approves",
                  "accountant": "Manager and owner both approve",
                  "no_manager_exception": (
                      "If the business has no approved manager, the owner's approval "
                      "is enough for an accountant.")},
    }
    if ctx.role == Role.OWNER:
        out["join_code"] = approvals.ensure_join_code(db, ctx.business)
        db.commit()
    return jsonable(out)


class DecisionIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


def _decide(db, ctx, membership_id: str, approve: bool, note: str | None):
    m = db.get(Membership, membership_id)
    if not m or m.business_id != ctx.business_id:
        raise HTTPException(404, "Request not found")
    try:
        res = approvals.decide(db, m, approver=ctx.user, approver_role=ctx.role,
                               approve=approve, note=note)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    audit(db, ctx, "membership.approve" if approve else "membership.reject",
          entity="membership", entity_id=m.id,
          detail={"role": m.role, "result": res})
    db.commit()
    return jsonable({"membership_id": m.id, **res})


@router.post("/{membership_id}/approve")
def approve(membership_id: str, db: DbDep, ctx: Tenant, body: DecisionIn | None = None):
    ctx.require(Role.MANAGER)
    return _decide(db, ctx, membership_id, True, body.note if body else None)


@router.post("/{membership_id}/reject")
def reject(membership_id: str, db: DbDep, ctx: Tenant, body: DecisionIn | None = None):
    ctx.require(Role.MANAGER)
    return _decide(db, ctx, membership_id, False, body.note if body else None)


@router.post("/join-code/rotate")
def rotate_join_code(db: DbDep, ctx: Tenant):
    """Issue a new code; the old one stops working immediately."""
    ctx.require(Role.OWNER)
    ctx.business.join_code = None
    code = approvals.ensure_join_code(db, ctx.business)
    audit(db, ctx, "business.join_code.rotate", entity="business", entity_id=ctx.business_id)
    db.commit()
    return {"join_code": code}
