import pytest
from pydantic import ValidationError

from src.core.clients.redis.models.run_delta import PendingDelta
from src.core.clients.redis.repositories.run_delta import RunDeltaRepository
from src.core.settings import Settings


async def test_delta_buffer_keeps_text_until_the_step_finishes(redis) -> None:
    deltas = RunDeltaRepository(redis)
    await deltas.append("r1", PendingDelta("analyst", None, 1, "Hel"), 60)
    await deltas.append("r1", PendingDelta("analyst", None, 1, "lo"), 60)
    await deltas.append("r1", PendingDelta("analyst.sub", "r0", 2, "x"), 60)

    pending = await deltas.pending("r1")
    await deltas.clear("r1", "analyst", None, 1)

    assert [(d.agent, d.text) for d in pending] == [
        ("analyst", "Hello"),
        ("analyst.sub", "x"),
    ]
    assert [d.agent for d in await deltas.pending("r1")] == ["analyst.sub"]
    assert await deltas.pending("other") == []


def test_scripted_llm_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="ASSISTANT_LLM"):
        Settings(
            JWT_SECRET_KEY="k",
            APP_ENV="production",
            ASSISTANT_LLM="fake",
        )
