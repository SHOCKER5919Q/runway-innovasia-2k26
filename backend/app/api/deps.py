from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.enums import MembershipStatus, Role
from app.core.security import decode_access_token
from app.models import AuditLog, Business, Membership, User

ROLE_POWER = {Role.VIEWER: 0, Role.ACCOUNTANT: 1, Role.MANAGER: 2, Role.OWNER: 3}

DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = decode_access_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class TenantContext:
    """Resolved business + the caller's role in it.

    Every tenant-scoped query in the API goes through ``ctx.business_id``.
    There is no code path that reads a business id straight from the body.
    """

    def __init__(self, user: User, business: Business, role: str, scopes: list[str]):
        self.user = user
        self.business = business
        self.business_id = business.id
        self.role = role
        self.scopes = scopes

    def require(self, min_role: str) -> None:
        if ROLE_POWER.get(self.role, -1) < ROLE_POWER.get(min_role, 99):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Requires role '{min_role}', caller has '{self.role}'")

    @property
    def can_write(self) -> bool:
        return ROLE_POWER.get(self.role, -1) >= ROLE_POWER[Role.MANAGER]


def get_tenant(
    db: DbDep,
    user: CurrentUser,
    x_business_id: Annotated[str | None, Header(alias="X-Business-Id")] = None,
) -> TenantContext:
    # Only approved memberships open a business. A pending manager or
    # accountant gets the same 403 as a stranger: no figure of any kind is
    # served until approvals.REQUIRED for their role is satisfied.
    q = select(Membership).where(Membership.user_id == user.id,
                                 Membership.status == MembershipStatus.APPROVED)
    if x_business_id:
        q = q.where(Membership.business_id == x_business_id)
    rows = db.scalars(q).all()
    if not rows:
        waiting = db.scalar(select(Membership).where(
            Membership.user_id == user.id, Membership.status == MembershipStatus.PENDING))
        if waiting is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Your access is waiting for approval. You will be able to "
                                "see this business once every required approver has agreed.")
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "No business membership for this user" if not x_business_id
                            else "You do not have access to this business")
    m = rows[0]
    biz = db.get(Business, m.business_id)
    if not biz:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return TenantContext(user, biz, m.role, list(m.scopes_json or []))


Tenant = Annotated[TenantContext, Depends(get_tenant)]


def audit(db: Session, ctx: TenantContext | None, action: str, *,
          entity: str | None = None, entity_id: str | None = None,
          detail: dict | None = None, request: Request | None = None) -> None:
    db.add(AuditLog(
        business_id=ctx.business_id if ctx else None,
        user_id=ctx.user.id if ctx else None,
        action=action, entity=entity, entity_id=entity_id,
        detail_json=detail or {},
        ip=(request.client.host if request and request.client else None),
    ))



def resolved_as_of(
    db: DbDep, ctx: Tenant,
    as_of: Annotated[str | None, Query(description="ISO date to evaluate as 'today'")] = None,
) -> date:
    """The as-of date for a request.

    An explicit ``as_of`` wins (point-in-time views, Settings override).
    Otherwise the books are shown as of the latest day the ledger has data
    for - so a statement imported for 12 Nov shows up as 12 Nov at once,
    instead of the screens staying on a pinned date or on a "today" with no
    data yet. Never later than today.
    """
    if as_of:
        return date.fromisoformat(as_of)
    from sqlalchemy import func
    from app.models import Invoice, Transaction
    t = db.scalar(select(func.max(Transaction.value_date)).where(
        Transaction.business_id == ctx.business_id))
    i = db.scalar(select(func.max(Invoice.issue_date)).where(
        Invoice.business_id == ctx.business_id))
    latest = max([d for d in (t, i) if d is not None], default=None)
    today = date.today()
    return min(latest, today) if latest else today
