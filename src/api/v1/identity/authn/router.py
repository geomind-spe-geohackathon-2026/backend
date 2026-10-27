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
from src.core.security.jwt import AccessTokenClaims

router = APIRouter(prefix="/authn", tags=["Authn"])

RevokedAccessTokenRepositoryDependency = Annotated[
    RevokedAccessTokenRepository,
    Depends(get_revoked_access_token_repository),
]
UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


@router.post(
    "/signup",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(
    credentials: schemas.Credentials,
    repository: UserRepositoryDependency,
) -> schemas.TokenResponse:
    return await services.signup_user(credentials, repository)


@router.post("/signin", response_model=schemas.TokenResponse)
async def signin(
    credentials: schemas.Credentials,
    repository: UserRepositoryDependency,
) -> schemas.TokenResponse:
    return await services.signin_user(credentials, repository)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout(
    request: Request,
    repository: RevokedAccessTokenRepositoryDependency,
) -> None:
    claims: AccessTokenClaims = request.state.access_token_claims
    await services.signout_user(claims, repository)


@router.post("/forgot-password", response_model=schemas.MessageResponse)
async def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    repository: UserRepositoryDependency,
) -> schemas.MessageResponse:
    return await services.request_password_reset(payload, repository)
