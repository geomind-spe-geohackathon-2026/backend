from pydantic import BaseModel, Field

from src.core.security.schemas import UserResponse


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str


class TokenResponse(TokenPairResponse):
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str
