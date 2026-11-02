import json

from src.core.clients.redis.client import RedisClient
from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.base import BaseRedisRepository

KEY_PREFIX = "run_delta"


def step_name(agent: str, parent: str | None, index: int) -> str:
    return json.dumps([agent, parent, index])


class RunDeltaRepository(BaseRedisRepository):
    """Short-lived buffer of the ``text.delta`` of running steps, for reconnects.

    geomind does not store text deltas. A step's text is appended here while it
    streams and deleted when the step finishes; every key expires on its own.
    """

    key_prefix = KEY_PREFIX

    def steps_key(self, run_id: str) -> str:
        return self.key(f"{run_id}:steps")

    def text_key(self, run_id: str, step: str) -> str:
        return self.key(f"{run_id}:text:{step}")

    async def append(
        self,
        run_id: str,
        delta: PendingDelta,
        expires_in: int,
    ) -> None:
        step = step_name(delta.agent, delta.parent, delta.index)
        text_key = self.text_key(run_id, step)
        await self.redis.append(text_key, delta.text)
        await self.redis.expire(text_key, expires_in)
        await self.redis.sadd(self.steps_key(run_id), step)
        await self.redis.expire(self.steps_key(run_id), expires_in)

    async def clear(self, run_id: str, agent: str, parent: str | None, index: int):
        """Forget the text of a step that finished."""
        step = step_name(agent, parent, index)
        await self.redis.delete(self.text_key(run_id, step))
        await self.redis.srem(self.steps_key(run_id), step)

    async def pending(self, run_id: str) -> list[PendingDelta]:
        """Return the text of every step still streaming, in step order."""
        pending = []
        for step in await self.redis.smembers(self.steps_key(run_id)):
            text = await self.redis.get(self.text_key(run_id, step))
            if text is None:
                continue
            agent, parent, index = json.loads(step)
            pending.append(PendingDelta(agent, parent, index, text))
        return sorted(pending, key=lambda delta: (delta.index, delta.agent))


def get_run_delta_repository(redis: RedisClient) -> RunDeltaRepository:
    return RunDeltaRepository(redis)
