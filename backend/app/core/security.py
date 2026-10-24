"""Password hashing and access tokens. No database or web imports.

Passwords use scrypt from the standard library (memory-hard, no extra
dependency). Stored format:  scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>
Parameters are stored with each hash so they can be raised later without
invalidating existing passwords.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_N, _R, _P = 2**14, 8, 1
_KEYLEN = 32
MAX_PASSWORD_BYTES = 1024  # scrypt cost is fine, but don't hash megabytes


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("password too long")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(raw, salt=salt, n=_N, r=_R, p=_P, dklen=_KEYLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """True if `password` matches `stored`. Never raises on malformed input."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        raw = password.encode("utf-8")
        if len(raw) > MAX_PASSWORD_BYTES:
            return False
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(
            raw, salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p),
            dklen=len(expected), maxmem=128 * 1024 * 1024,
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


# A real hash to check against when the email is unknown, so login takes about
# as long for unknown and known emails (no user enumeration by timing).
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def create_access_token(user_id: uuid.UUID, role: str, *, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {
        "typ": "access",
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    """The user id in a valid, unexpired token, else None.

    Only the subject is trusted from the token. The role is always re-read
    from the database so a demoted or suspended user loses access at once.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],  # fixed list: no alg=none / alg confusion
            options={"require": ["exp", "sub", "typ"]},
        )
        # Booking links are signed with the same key; they must never work as logins.
        if payload["typ"] != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


# ------------------------------------------------------------ booking links


@dataclass(frozen=True)
class BookingClaims:
    candidate_id: uuid.UUID
    drive_id: uuid.UUID
    stage_id: uuid.UUID


def create_booking_token(
    candidate_id: uuid.UUID, drive_id: uuid.UUID, stage_id: uuid.UUID,
    *, ttl: timedelta, now: datetime | None = None,
) -> str:
    """A signed, expiring link token that lets one candidate book one round of one drive.

    It carries no login rights: `decode_access_token` rejects it (typ != "access").
    """
    now = now or datetime.now(timezone.utc)
    payload = {
        "typ": "booking",
        "sub": str(candidate_id),
        "drv": str(drive_id),
        "stg": str(stage_id),
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_booking_token(token: str) -> BookingClaims | None:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "typ", "drv", "stg"]},
        )
        if payload["typ"] != "booking":
            return None
        return BookingClaims(
            uuid.UUID(payload["sub"]), uuid.UUID(payload["drv"]), uuid.UUID(payload["stg"])
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
