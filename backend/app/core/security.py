"""Password hashing, JWT issuance and a small in-process rate limiter.

Password hashing uses PBKDF2-HMAC-SHA256 from the standard library rather
than bcrypt/argon2: it removes a native build dependency and, at the
iteration count configured in ``Settings``, is an accepted choice (NIST
SP 800-63B). ``SECURITY.md`` records argon2id as the production target.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_ALGO = "sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode(), salt, settings.pbkdf2_iterations)
    return f"pbkdf2_{_ALGO}${settings.pbkdf2_iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt_hex, dk_hex = stored.split("$")
        if not scheme.startswith("pbkdf2_"):
            return False
        dk = hashlib.pbkdf2_hmac(scheme.split("_", 1)[1], password.encode(),
                                 bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def create_access_token(*, user_id: str, email: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "email": email, "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "iss": "runway", **(extra or {}),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm], issuer="runway")
    except jwt.PyJWTError:
        return None


class RateLimiter:
    """Fixed-window-free sliding counter. Per-process only; production uses
    a shared store (see SECURITY.md)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > 60.0:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True


rate_limiter = RateLimiter(settings.rate_limit_per_minute)
