from pydantic import BaseModel, ConfigDict


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_approve: bool


class Preferences(BaseModel):
    """A user's assistant preferences (QA-292).

    ``auto_approve`` is what new chats start with; ``auto_approve_set`` is false until the user
    has answered once, so the chat asks only then.
    """

    auto_approve: bool
    auto_approve_set: bool
