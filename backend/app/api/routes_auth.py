from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, Tenant, audit
from app.core.enums import Role
from app.core.security import create_access_token, hash_password, rate_limiter, verify_password
from app.models import Business, Membership, User, _uid

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=200)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=160)
    business_name: str | None = Field(default=None, max_length=200)
    industry: str = "wholesale_distribution"


def _session_payload(db, user: User) -> dict:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    businesses = []
    for m in memberships:
        b = db.get(Business, m.business_id)
        if b:
            businesses.append({"id": b.id, "name": b.name, "industry": b.industry,
                               "role": m.role, "is_demo": b.is_demo,
                               "demo_scenario": b.demo_scenario, "city": b.city})
    return {
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
    user = User(id=_uid(), email=body.email.lower(), full_name=body.full_name,
                password_hash=hash_password(body.password))
    db.add(user)
    if body.business_name:
        biz = Business(id=_uid(), name=body.business_name, industry=body.industry,
                       is_demo=False, safety_buffer_paise=0)
        db.add(biz)
        db.flush()
        db.add(Membership(id=_uid(), user_id=user.id, business_id=biz.id, role=Role.OWNER,
                          scopes_json=["read:*", "write:*"]))
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
