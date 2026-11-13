from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, Tenant, audit
from app.core import approvals
from app.core.enums import AccountKind, MembershipStatus, Role
from app.core.security import create_access_token, hash_password, rate_limiter, verify_password
from app.models import Account, AuditLog as AuditLog_, Business, Membership, User, _uid

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=160)
    # owner: creates a new business (business_name required).
    # manager / accountant: asks to join one with the owner's join code and
    # stays pending until approvals.REQUIRED[role] have all approved.
    role: str = Role.OWNER
    business_name: str | None = Field(default=None, max_length=200)
    join_code: str | None = Field(default=None, max_length=16)
    industry: str = "wholesale_distribution"
    city: str | None = Field(default=None, max_length=80)
    gstin: str | None = Field(default=None, max_length=15)
    safety_buffer_paise: int = Field(default=0, ge=0)
    opening_balance_paise: int = Field(default=0)
    overdraft_limit_paise: int = Field(default=0, ge=0)
    restricted_paise: int = Field(default=0, ge=0)
    account_name: str = Field(default="Primary Bank Account", min_length=1, max_length=160)
    bank_name: str | None = Field(default=None, max_length=120)


def _session_payload(db, user: User) -> dict:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    businesses, pending = [], []
    for m in memberships:
        b = db.get(Business, m.business_id)
        if not b:
            continue
        if m.status == MembershipStatus.APPROVED:
            businesses.append({"id": b.id, "name": b.name, "industry": b.industry,
                               "role": m.role, "is_demo": b.is_demo,
                               "demo_scenario": b.demo_scenario, "city": b.city})
        else:
            # Name and status only - no figures leave the business before approval.
            pending.append({"business_name": b.name, "role": m.role, "status": m.status,
                            "waiting_for": approvals.outstanding(db, m)
                            if m.status == MembershipStatus.PENDING else [],
                            "approvals": m.approvals_json or []})
    return {
        "pending_memberships": pending,
        "token": create_access_token(user_id=user.id, email=user.email),
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name,
                 "is_accountant": user.is_accountant,
                 "preferred_language": user.preferred_language},
        "businesses": businesses,
        "active_business_id": businesses[0]["id"] if businesses else None,
    }


@router.post("/login")
def login(body: LoginIn, db: DbDep, request: Request):
    if not rate_limiter.allow(f"login:{request.client.host if request.client else 'anon'}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try again shortly")
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Constant-ish work either way so a wrong email is not distinguishable by timing.
    ok = verify_password(body.password, user.password_hash) if user else verify_password(
        body.password, "pbkdf2_sha256$1$00$00")
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    return _session_payload(db, user)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: DbDep):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")
    role = (body.role or Role.OWNER).lower()
    if role not in (Role.OWNER, Role.MANAGER, Role.ACCOUNTANT):
        raise HTTPException(422, "role must be owner, manager or accountant")
    biz = None
    if role == Role.OWNER:
        if not (body.business_name or "").strip():
            raise HTTPException(422, "An owner account needs a business name")
    else:
        code = (body.join_code or "").strip().upper()
        biz = db.scalar(select(Business).where(Business.join_code == code)) if code else None
        if biz is None:
            raise HTTPException(422, "That join code does not match any business. "
                                     "Ask the owner for the code shown in Settings - Team.")
    user = User(id=_uid(), email=body.email.lower(), full_name=body.full_name,
                password_hash=hash_password(body.password),
                is_accountant=(role == Role.ACCOUNTANT))
    db.add(user)
    db.flush()
    if role == Role.OWNER:
        biz = Business(
            id=_uid(), name=body.business_name.strip(), industry=body.industry,
            city=body.city.strip() if body.city else None,
            gstin=body.gstin.strip().upper() if body.gstin else None,
            is_demo=False, safety_buffer_paise=body.safety_buffer_paise,
        )
        db.add(biz)
        db.flush()
        approvals.ensure_join_code(db, biz)
        db.add(Membership(id=_uid(), user_id=user.id, business_id=biz.id, role=Role.OWNER,
                          scopes_json=["read:*", "write:*"],
                          status=MembershipStatus.APPROVED, approvals_json=[]))
        db.add(Account(
            id=_uid(), business_id=biz.id, name=body.account_name.strip(),
            kind=AccountKind.CURRENT, bank_name=body.bank_name.strip() if body.bank_name else None,
            opening_balance_paise=body.opening_balance_paise,
            # Early enough that the owner's past statements are not refused
            # by the import date guard (rows before an account opened).
            opening_date=date(2000, 1, 1),
            overdraft_limit_paise=body.overdraft_limit_paise,
            restricted_paise=body.restricted_paise,
            source_system="manual",
        ))
    else:
        m = Membership(id=_uid(), user_id=user.id, business_id=biz.id, role=role,
                       scopes_json=["read:*", "write:*"],
                       status=MembershipStatus.PENDING, approvals_json=[])
        db.add(m)
        db.flush()
        db.add(AuditLog_(business_id=biz.id, user_id=user.id, action="membership.request",
                         entity="membership", entity_id=m.id,
                         detail_json={"role": role,
                                      "requires": approvals.required_for(db, m)}))
    db.commit()
    return _session_payload(db, user)


@router.get("/me")
def me(db: DbDep, user: CurrentUser):
    return _session_payload(db, user)


@router.get("/demo-accounts")
def demo_accounts():
    """Published so the demo is reproducible. Demo credentials only."""
    return {"accounts": [
        {"email": "owner@runway.demo", "password": "demo1234", "role": "Business owner",
         "name": "Amit Sharma", "sees": "Everything for Sri Lakshmi Industrial Supplies"},
        {"email": "manager@runway.demo", "password": "demo1234", "role": "Manager",
         "name": "Priya Reddy", "sees": "Same business, cannot change policy settings"},
        {"email": "ca@runway.demo", "password": "demo1234", "role": "Chartered accountant",
         "name": "S. Krishnan, FCA",
         "sees": "A multi-business portfolio view across both demo businesses"}],
        "note": ("These exist only in the demo workspace. Production authentication is "
                 "separate and is described in docs/SECURITY.md.")}
