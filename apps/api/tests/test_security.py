import uuid

import jwt
import pytest

from security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_is_not_plaintext_and_verifies():
    hashed = hash_password("correcthorsebatterystaple")

    assert hashed != "correcthorsebatterystaple"
    assert verify_password("correcthorsebatterystaple", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trips_claims():
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()

    token = create_access_token(user_id=user_id, role="parent", family_id=family_id)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "parent"
    assert payload["family_id"] == str(family_id)


def test_access_token_without_family_id_is_null():
    token = create_access_token(user_id=uuid.uuid4(), role="staff", family_id=None)

    payload = decode_access_token(token)

    assert payload["family_id"] is None


def test_decode_rejects_tampered_token():
    token = create_access_token(user_id=uuid.uuid4(), role="staff", family_id=None)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token + "tampered")
