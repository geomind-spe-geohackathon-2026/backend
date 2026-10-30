from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from src.core.security.errors import TokenValidationError, UnauthorizedError
from src.core.settings import settings

ACCESS_CLAIMS = ["sub", "jti", "rid", "type", "iat", "exp", "iss", "aud"]
REFRESH_CLAIMS = ["sub", "jti", "type", "iat", "exp", "iss", "aud"]


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    subject: UUID
    token_id: str
    refresh_token_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    subject: UUID
    token_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


def encode_token(subject: UUID, token_id: str, lifetime: timedelta, **claims) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "jti": token_id,
        "iat": now,
        "exp": now + lifetime,
        "iss": settings.APP_NAME,
        "aud": settings.APP_NAME,
        **claims,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_token_pair(subject: UUID) -> TokenPair:
    """Create tokens that know each other, so logout can revoke both."""
    refresh_token_id = uuid4().hex
    access_lifetime = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_lifetime = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return TokenPair(
        access_token=encode_token(
            subject,
            uuid4().hex,
            access_lifetime,
            type="access",
            rid=refresh_token_id,
        ),
        refresh_token=encode_token(
            subject,
            refresh_token_id,
            refresh_lifetime,
            type="refresh",
        ),
    )


def decode_payload(token: str, token_type: str, required: list[str]) -> dict:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        audience=settings.APP_NAME,
        issuer=settings.APP_NAME,
        options={"require": required},
    )
    if payload["type"] != token_type:
        raise TokenValidationError("Invalid token type")
    return payload


def decode_access_token(token: str) -> AccessTokenClaims:
    try:
        payload = decode_payload(token, "access", ACCESS_CLAIMS)
        return AccessTokenClaims(
            subject=UUID(payload["sub"]),
            token_id=payload["jti"],
            refresh_token_id=payload["rid"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("Invalid or expired token") from exc


def decode_refresh_token(token: str) -> RefreshTokenClaims:
    try:
        payload = decode_payload(token, "refresh", REFRESH_CLAIMS)
        return RefreshTokenClaims(
            subject=UUID(payload["sub"]),
            token_id=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise TokenValidationError("Invalid or expired token") from exc


def verify_access_token(authorization: str) -> tuple[str, AccessTokenClaims]:
    scheme, _, access_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not access_token.strip():
        raise UnauthorizedError("Missing bearer token")

    access_token = access_token.strip()
    try:
        claims = decode_access_token(access_token)
    except TokenValidationError:
        raise UnauthorizedError("Invalid or expired token") from None
    return access_token, claims
