from uuid import uuid4

import pytest

from src.core.security.errors import TokenValidationError
from src.core.security.jwt import (
    create_token_pair,
    decode_access_token,
    decode_refresh_token,
)
from src.core.security.passwords import hash_password, verify_password


def test_access_token_round_trip() -> None:
    user_id = uuid4()

    tokens = create_token_pair(user_id)
    claims = decode_access_token(tokens.access_token)

    assert claims.subject == user_id
    assert (
        claims.refresh_token_id == decode_refresh_token(tokens.refresh_token).token_id
    )


def test_refresh_token_is_not_an_access_token() -> None:
    tokens = create_token_pair(uuid4())

    with pytest.raises(TokenValidationError):
        decode_access_token(tokens.refresh_token)
    with pytest.raises(TokenValidationError):
        decode_refresh_token(tokens.access_token)


def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(TokenValidationError):
        decode_access_token("invalid-token")


def test_password_hashing() -> None:
    hashed_password = hash_password("correct-password")

    assert hashed_password != "correct-password"
    assert verify_password("correct-password", hashed_password)
    assert not verify_password("wrong-password", hashed_password)
