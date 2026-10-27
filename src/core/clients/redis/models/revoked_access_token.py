from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RevokedAccessToken:
    token_id: str
    expires_at: datetime
