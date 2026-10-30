from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from src.api.v1.identity.authn import schemas, services
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
    get_revoked_access_token_repository,
)
from src.core.security.access import CurrentUser
from src.core.security.jwt import AccessTokenClaims

router = APIRouter(prefix="/authn", tags=["Authn"])

RevokedAccessTokenRepositoryDependency = Annotated[
    RevokedAccessTokenRepository,
    Depends(get_revoked_access_token_repository),
]
UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


@router.post("/login", response_model=schemas.TokenResponse)
async def login(
    credentials: schemas.Credentials,
    repository: UserRepositoryDependency,
) -> schemas.TokenResponse:
    return await services.login_user(credentials, repository)


@router.post("/refresh", response_model=schemas.TokenPairResponse)
async def refresh(
    payload: schemas.RefreshRequest,
    users: UserRepositoryDependency,
    revoked_tokens: RevokedAccessTokenRepositoryDependency,
) -> schemas.TokenPairResponse:
    return await services.refresh_tokens(payload, users, revoked_tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    _user: CurrentUser,
    repository: RevokedAccessTokenRepositoryDependency,
) -> None:
    claims: AccessTokenClaims = request.state.access_token_claims
    await services.logout_user(claims, repository)
