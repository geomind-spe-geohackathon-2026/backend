from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from src.core.clients.postgres.client import get_db

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
