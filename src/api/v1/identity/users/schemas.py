from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "member"]


class UserUpdate(BaseModel):
    role: Literal["admin", "member"] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
