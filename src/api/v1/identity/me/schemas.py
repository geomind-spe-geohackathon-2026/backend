from pydantic import BaseModel, Field


class ChangePassword(BaseModel):
    old_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
