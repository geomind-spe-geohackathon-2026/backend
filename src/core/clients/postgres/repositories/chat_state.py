from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.clients.postgres.models.chat_state import ChatState
from src.core.clients.postgres.repositories.base import BaseRepository, DatabaseSession
from src.core.errors import ConflictError


class ChatStateRepository(BaseRepository):
    async def latest(self, chat_id: UUID) -> ChatState | None:
        statement = (
            select(ChatState)
            .where(ChatState.chat_id == chat_id)
            .order_by(ChatState.version.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def save(self, chat_id: UUID, state: dict[str, Any]) -> ChatState:
        """Save the state as the next version of the chat."""
        latest = await self.latest(chat_id)
        row = ChatState(
            chat_id=chat_id,
            version=latest.version + 1 if latest else 1,
            state=state,
        )
        self.session.add(row)
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("State version is taken") from error
        return row


def get_chat_state_repository(session: DatabaseSession) -> ChatStateRepository:
    return ChatStateRepository(session)
