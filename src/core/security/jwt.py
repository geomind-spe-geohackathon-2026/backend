from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from src.core.security.errors import TokenValidationError, UnauthorizedError
from src.core.settings import settings


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    subject: UUID
    token_id: str
    expires_at: datetime


def create_access_token(subject: UUID) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(subject),
        "jti": uuid4().hex,
        "type": "access",
        "iat": now,
        "exp": expires_at,
        "iss": settings.APP_NAME,
        "aud": settings.APP_NAME,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.APP_NAME,
            issuer=settings.APP_NAME,
            options={"require": ["sub", "jti", "type", "iat", "exp", "iss", "aud"]},
        )
        if payload["type"] != "access":
            raise TokenValidationError("Invalid token type")
        return AccessTokenClaims(
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
