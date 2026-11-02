from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from src.core.sse.events import StreamEvent, encode_event


def publish_event(redis: Redis, channel: str, event: StreamEvent) -> None:
    """Publish from a worker or a worker thread. Store the event before publishing."""
    redis.publish(channel, encode_event(event))


async def publish_event_async(
    redis: AsyncRedis,
    channel: str,
    event: StreamEvent,
) -> None:
    await redis.publish(channel, encode_event(event))
