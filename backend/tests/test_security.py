"""Password hashing and tokens. No database needed."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core import security
from app.core.config import settings


def test_hash_roundtrip_and_salting():
    h1, h2 = security.hash_password("correct horse battery"), security.hash_password("correct horse battery")
    assert h1 != h2  # random salt
    assert security.verify_password("correct horse battery", h1)
    assert not security.verify_password("correct horse batterz", h1)


def test_verify_never_raises_on_garbage():
    for bad in ["", "plain", "scrypt$x$y$z$a$b", "bcrypt$1$2$3$4$5", "scrypt$16384$8$1$!!$!!"]:
        assert security.verify_password("anything", bad) is False


def test_oversized_password_rejected_not_hashed():
    huge = "a" * (security.MAX_PASSWORD_BYTES + 1)
    assert security.verify_password(huge, security.DUMMY_HASH) is False


def test_token_roundtrip():
    uid = uuid.uuid4()
    assert security.decode_access_token(security.create_access_token(uid, "coordinator")) == uid


def test_expired_token_rejected():
    uid = uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES + 5)
    assert security.decode_access_token(security.create_access_token(uid, "coordinator", now=old)) is None


def test_wrong_key_and_alg_none_rejected():
    uid = uuid.uuid4()
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    forged = jwt.encode({"sub": str(uid), "exp": exp}, "some-other-key-that-is-long-enough-123456", algorithm="HS256")
    assert security.decode_access_token(forged) is None
    unsigned = jwt.encode({"sub": str(uid), "exp": exp}, None, algorithm="none")
    assert security.decode_access_token(unsigned) is None


def test_token_without_exp_or_with_bad_sub_rejected():
    no_typ = jwt.encode({"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                        settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert security.decode_access_token(no_typ) is None
    no_exp = jwt.encode({"sub": str(uuid.uuid4()), "typ": "access"}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert security.decode_access_token(no_exp) is None
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    bad_sub = jwt.encode({"sub": "not-a-uuid", "exp": exp}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert security.decode_access_token(bad_sub) is None
    assert security.decode_access_token("not.a.jwt") is None


def test_booking_token_roundtrip_and_is_not_a_login():
    c, d, st = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tok = security.create_booking_token(c, d, st, ttl=timedelta(hours=1))
    claims = security.decode_booking_token(tok)
    assert (claims.candidate_id, claims.drive_id, claims.stage_id) == (c, d, st)
    assert security.decode_access_token(tok) is None          # cannot be used as a bearer login
    assert security.decode_booking_token(security.create_access_token(c, "candidate")) is None


def test_expired_or_tampered_booking_token_rejected():
    c, d, st = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    assert security.decode_booking_token(security.create_booking_token(c, d, st, ttl=timedelta(hours=1), now=old)) is None
    tok = security.create_booking_token(c, d, st, ttl=timedelta(hours=1))
    assert security.decode_booking_token(tok[:-3] + ("AAA" if not tok.endswith("AAA") else "BBB")) is None
