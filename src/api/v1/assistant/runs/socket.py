from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import WebSocket
from src.api.v1.assistant.runs.services import follow_run_events
from src.core.assistant.access import run_from_path
from src.core.assistant.errors import RunNotFoundError
from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.clients.postgres.repositories.run import RunRepository
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.security.access import require_token_holder
from src.core.security.errors import (
    AuthenticationUnavailableError,
    UnauthorizedError,
)
from src.core.security.middleware import verify_live_token
from src.core.socket.relay import (
    CLOSE_FAILED,
    CLOSE_NOT_FOUND,
    CLOSE_UNAUTHORIZED,
    read_hello,
    relay,
)


async def require_run(
    run_id: UUID,
    token: str,
    redis: Redis | None,
    session: AsyncSession,
) -> None:
    """Refuse a token or a run the way the HTTP routes refuse them.

    The HTTP middleware does not see a socket, so the same checks run here.
    """
    _, claims = await verify_live_token(f"Bearer {token}", redis)
    user = await UserRepository(session).get_by_id(claims.subject)
    user = require_token_holder(user, claims.issued_at)
    await run_from_path(
        run_id, user, RunRepository(session), ProjectRepository(session)
    )


async def serve_run(websocket: WebSocket, run_id: UUID) -> None:
    """Send a run's events over a socket: the same events and order as its SSE stream.

    The client's first message is a ``Hello``; the session used to check it is closed
    before the stream starts, so a long run holds no database connection.
    """
    await websocket.accept()
    hello = await read_hello(websocket)
    if hello is None:
        return
    redis = websocket.app.state.redis
    factory = websocket.app.state.postgres_session_factory
    try:
        async with factory() as session:
            await require_run(run_id, hello.token, redis, session)
    except UnauthorizedError:
        await websocket.close(CLOSE_UNAUTHORIZED)
        return
    except RunNotFoundError:
        await websocket.close(CLOSE_NOT_FOUND)
        return
    except AuthenticationUnavailableError:
        await websocket.close(CLOSE_FAILED)
        return
    await relay(websocket, follow_run_events(run_id, redis, factory, hello.after))
