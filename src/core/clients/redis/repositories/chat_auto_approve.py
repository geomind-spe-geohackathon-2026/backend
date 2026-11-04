from redis import Redis as SyncRedis

from src.core.clients.redis.repositories.base import BaseRedisRepository

KEY_PREFIX = "chat_auto_approve"
ON = "on"


class ChatAutoApproveRepository(BaseRedisRepository):
    """A chat's auto-approve setting: on, the worker approves its runs' tool calls (QA-031).

    Kept without expiry; a lost key reads as off, the safe side.
    """

    key_prefix = KEY_PREFIX

    async def is_on(self, chat_id: str) -> bool:
        return await self.get(chat_id) == ON

    async def turn(self, chat_id: str, on: bool) -> None:
        if on:
            await self.set(chat_id, ON)
        else:
            await self.delete(chat_id)


def auto_approve_on(redis: SyncRedis, chat_id: str) -> bool:
    """The same setting for a Celery worker, which cannot await."""
    return redis.get(f"{KEY_PREFIX}:{chat_id}") == ON
