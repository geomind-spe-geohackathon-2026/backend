from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.v1.assistant.preferences import schemas
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.security.access import CurrentUser

router = APIRouter(prefix="/preferences", tags=["Preferences"])

UserRepositoryDependency = Annotated[UserRepository, Depends(get_user_repository)]


def preferences_of(user: User) -> schemas.Preferences:
    return schemas.Preferences(
        auto_approve=bool(user.auto_approve),
        auto_approve_set=user.auto_approve is not None,
    )


@router.get("", response_model=schemas.Preferences)
async def read_preferences(user: CurrentUser) -> schemas.Preferences:
    """The user's assistant preferences; new chats take ``auto_approve`` (QA-292)."""
    return preferences_of(user)


@router.put("", response_model=schemas.Preferences)
async def set_preferences(
    payload: schemas.PreferencesUpdate,
    user: CurrentUser,
    users: UserRepositoryDependency,
) -> schemas.Preferences:
    """Save the user's answer; chats created afterwards start with it."""
    stored = await users.get_by_id(user.id)
    updated = await users.update(stored or user, {"auto_approve": payload.auto_approve})
    return preferences_of(updated)
