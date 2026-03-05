"""Unit tests for app/core/security.py — no database required."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import TokenClaims


# ---------- hash_password / verify_password ----------

def test_hash_password_is_not_plaintext():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert len(hashed) > 0


def test_verify_password_correct():
    hashed = hash_password("correct-horse")
    assert verify_password("correct-horse", hashed) is True


def test_verify_password_wrong_returns_false():
    hashed = hash_password("correct-horse")
    assert verify_password("wrong-horse", hashed) is False


def test_same_password_produces_different_hashes():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # bcrypt/argon2 salts differ


# ---------- create_access_token ----------

def test_create_access_token_returns_bearer_response():
    claims = TokenClaims(tenant_id=uuid.uuid4(), user_id=uuid.uuid4())
    response = create_access_token(claims)
    assert response.access_token
    assert response.token_type == "bearer"


def test_create_access_token_encodes_claims():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    claims = TokenClaims(tenant_id=tenant_id, user_id=user_id)

    response = create_access_token(claims)
    payload = jwt.decode(
        response.access_token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert uuid.UUID(payload["tenant_id"]) == tenant_id
    assert uuid.UUID(payload["user_id"]) == user_id


# ---------- decode_access_token ----------

def test_decode_access_token_round_trip():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    claims = TokenClaims(tenant_id=tenant_id, user_id=user_id)
    token = create_access_token(claims).access_token

    decoded = decode_access_token(token)
    assert decoded.tenant_id == tenant_id
    assert decoded.user_id == user_id


def test_decode_access_token_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Invalid token"):
        decode_access_token("not.a.valid.token")


def test_decode_access_token_wrong_signature_raises_value_error():
    claims = TokenClaims(tenant_id=uuid.uuid4(), user_id=uuid.uuid4())
    token = create_access_token(claims).access_token
    tampered = token[:-4] + "xxxx"
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_decode_access_token_expired_raises_value_error():
    payload = {
        "tenant_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        "iat": datetime.now(timezone.utc) - timedelta(minutes=30),
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(ValueError, match="Token expired"):
        decode_access_token(expired_token)
