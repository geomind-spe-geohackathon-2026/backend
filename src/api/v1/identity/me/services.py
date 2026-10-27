from uuid import UUID

from src.core.clients.postgres.repositories.user import UserRepository


async def delete_account(user_id: UUID, repository: UserRepository) -> None:
    await repository.delete_by_id(user_id)
