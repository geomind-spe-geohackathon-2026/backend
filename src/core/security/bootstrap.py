from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.clients.postgres.repositories.user import UserRepository
from src.core.logging.logger import get_logger
from src.core.security.emails import normalize_email
from src.core.security.passwords import hash_password
from src.core.settings import settings

logger = get_logger(__name__)


async def ensure_first_admin(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Create the admin from settings when no admin exists yet."""
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        return

    async with session_factory() as session:
        repository = UserRepository(session)
        if await repository.has_admin():
            return
        try:
            await repository.create(
                normalize_email(settings.FIRST_ADMIN_EMAIL),
                hash_password(settings.FIRST_ADMIN_PASSWORD),
                name="Administrator",
                role="admin",
            )
        except IntegrityError:
            logger.warning("First admin email is taken; no admin was created")
            return
    logger.info("First admin created")
