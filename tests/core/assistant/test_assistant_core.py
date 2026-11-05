import pytest
from pydantic import ValidationError

from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.settings import Settings


async def test_delta_buffer_keeps_text_until_the_step_finishes(redis) -> None:
    deltas = RunDeltaRepository(redis)
    first = PendingDelta("analyst", None, 1, "Hel", "s1", None)
    await deltas.append("r1", first, 60)
    await deltas.append("r1", PendingDelta("analyst", None, 1, "lo", "s1", None), 60)
    await deltas.append("r1", PendingDelta("analyst.sub", "r0", 2, "x", "s2", None), 60)

    pending = await deltas.pending("r1")
    await deltas.clear("r1", first)

    assert [(d.agent, d.text) for d in pending] == [
        ("analyst", "Hello"),
        ("analyst.sub", "x"),
    ]
    assert [d.agent for d in await deltas.pending("r1")] == ["analyst.sub"]
    assert await deltas.pending("other") == []


async def test_parallel_instances_keep_their_own_text(redis) -> None:
    deltas = RunDeltaRepository(redis)
    one = PendingDelta("geoscientist", "r0", 1, "first", "s1", "Geoscientist I")
    two = PendingDelta("geoscientist", "r0", 1, "second", "s2", "Geoscientist II")
    await deltas.append("r1", one, 60)
    await deltas.append("r1", two, 60)

    pending = await deltas.pending("r1")
    await deltas.clear("r1", one)

    assert sorted((d.session, d.instance, d.text) for d in pending) == [
        ("s1", "Geoscientist I", "first"),
        ("s2", "Geoscientist II", "second"),
    ]
    assert [d.text for d in await deltas.pending("r1")] == ["second"]


async def test_a_step_buffered_before_sessions_reads_back(redis) -> None:
    deltas = RunDeltaRepository(redis)
    await redis.sadd(deltas.steps_key("r1"), '["analyst", null, 1]')
    await redis.set(deltas.text_key("r1", '["analyst", null, 1]'), "old")

    assert await deltas.pending("r1") == [
        PendingDelta("analyst", None, 1, "old", None, None)
    ]


def test_scripted_llm_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="ASSISTANT_LLM"):
        Settings(
            JWT_SECRET_KEY="k",
            APP_ENV="production",
            ASSISTANT_LLM="fake",
        )
