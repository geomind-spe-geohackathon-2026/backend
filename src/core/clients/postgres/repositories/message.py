from uuid import UUID

from sqlalchemy import select

from src.core.clients.postgres.models.message import Message
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.pagination.page import PageRequest, paginate


class MessageRepository(BaseRepository):
    async def add(
        self,
        chat_id: UUID,
        role: str,
        content: str,
        run_id: UUID | None,
        suggestions: list[dict[str, str]] | None = None,
    ) -> Message:
        message = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            run_id=run_id,
            suggestions=suggestions or None,
        )
        self.session.add(message)
        await self.session.commit()
        return message

    async def for_run(self, run_id: UUID, role: str) -> Message | None:
        """Return the message of a role that belongs to a run."""
        statement = select(Message).where(
            Message.run_id == run_id,
            Message.role == role,
        )
        return await self.session.scalar(statement.limit(1))

    async def list_page(self, chat_id: UUID, page: PageRequest) -> list[Message]:
        """List messages, oldest first."""
        statement = select(Message).where(Message.chat_id == chat_id)
        statement = paginate(statement, Message.created, Message.id, page)
        return list(await self.session.scalars(statement))

    async def history(self, chat_id: UUID) -> list[Message]:
        """List every message of a chat, oldest first, for the agent's history."""
        statement = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created, Message.id)
        )
        return list(await self.session.scalars(statement))


def get_message_repository(session: DatabaseSession) -> MessageRepository:
    return MessageRepository(session)
