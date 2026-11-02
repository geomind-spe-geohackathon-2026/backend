import json
from dataclasses import dataclass
from typing import Any

from src.core.settings import settings


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """One event of a stream.

    ``sequence`` is the stored order and becomes the SSE ``id``; an event that is
    never stored (a text delta) has none, is never replayed and carries no id.
    """

    type: str
    data: dict[str, Any]
    sequence: int | None = None


def channel_name(kind: str, identifier: str) -> str:
    """Return the Redis channel of a stream: environment, kind and id."""
    return f"{settings.APP_ENV}:{kind}:{identifier}"


def encode_event(event: StreamEvent) -> str:
    return json.dumps(
        {"type": event.type, "data": event.data, "sequence": event.sequence}
    )


def decode_event(text: str) -> StreamEvent:
    body = json.loads(text)
    return StreamEvent(type=body["type"], data=body["data"], sequence=body["sequence"])
