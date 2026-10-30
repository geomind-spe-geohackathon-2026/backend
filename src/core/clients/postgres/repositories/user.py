from typing import Annotated, Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends
from src.core.clients.postgres.client import get_db
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.base import BaseRepository
from src.core.pagination.page import PageRequest, paginate

DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id, populate_existing=True)

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def has_admin(self) -> bool:
        return bool(
            await self.session.scalar(select(exists().where(User.role == "admin")))
        )

    async def list_page(self, page: PageRequest) -> list[User]:
        statement = paginate(select(User), User.created_at, User.id, page)
        return list(await self.session.scalars(statement))

    async def create(
        self,
        email: str,
        password_hash: str,
        name: str = "",
        role: str = "member",
    ) -> User:
        user = User(email=email, password_hash=password_hash, name=name, role=role)
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user

    async def update(self, user: User, values: dict[str, Any]) -> User:
        for field, value in values.items():
            setattr(user, field, value)
        await self.session.commit()
        return user


def get_user_repository(session: DatabaseSession) -> UserRepository:
    return UserRepository(session)
