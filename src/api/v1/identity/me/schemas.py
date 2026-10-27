from pydantic import BaseModel


class AccountDeletionResponse(BaseModel):
    message: str
