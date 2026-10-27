from typing import Annotated
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from src.core.clients.postgres.client import get_db
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.base import BaseRepository

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


class UserRepository(BaseRepository):
    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def create(self, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user

    async def delete_by_id(self, user_id: UUID) -> None:
        await self.session.execute(delete(User).where(User.id == user_id))
        await self.session.commit()


def get_user_repository(session: DatabaseSession) -> UserRepository:
    return UserRepository(session)
