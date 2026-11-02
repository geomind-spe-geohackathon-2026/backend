from uuid import UUID

from sqlalchemy import delete, select

from src.core.clients.postgres.client import utc_now
from src.core.clients.postgres.models.chat import Chat
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class ChatRepository(BaseRepository):
    async def create(self, project_id: UUID, title: str, author_id: UUID) -> Chat:
        chat = Chat(project_id=project_id, title=title, author_id=author_id)
        self.session.add(chat)
        await self.session.commit()
        return chat

    async def get_by_id(self, chat_id: UUID) -> Chat | None:
        return await self.session.get(Chat, chat_id)

    async def list_page(self, project_id: UUID, page: PageRequest) -> list[Chat]:
        statement = select(Chat).where(Chat.project_id == project_id)
        statement = paginate(statement, Chat.created, Chat.id, page)
        return list(await self.session.scalars(statement))

    async def latest(self, project_id: UUID, limit: int) -> list[Chat]:
        """Return the chats changed last, newest first."""
        statement = (
            select(Chat)
            .where(Chat.project_id == project_id)
            .order_by(Chat.updated.desc(), Chat.id)
            .limit(limit)
        )
        return list(await self.session.scalars(statement))

    async def rename(self, chat: Chat, title: str) -> Chat:
        chat.title = title
        await self.session.commit()
        return chat

    async def touch(self, chat: Chat) -> Chat:
        """Mark the chat as changed now, so it sorts first among the latest."""
        chat.updated = utc_now()
        await self.session.commit()
        return chat

    async def delete(self, chat_id: UUID) -> None:
        await self.session.execute(delete(Chat).where(Chat.id == chat_id))
        await self.session.commit()


def get_chat_repository(session: DatabaseSession) -> ChatRepository:
    return ChatRepository(session)
