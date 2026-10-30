from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute

from fastapi import Depends, Query
from src.core.errors import ValidationFailedError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    items: list[T]
    next: str | None


@dataclass(frozen=True, slots=True)
class PageRequest:
    limit: int = DEFAULT_LIMIT
    after: tuple[datetime, UUID] | None = None


def encode_cursor(created: datetime, row_id: UUID) -> str:
    return urlsafe_b64encode(f"{created.isoformat()}|{row_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        created, row_id = urlsafe_b64decode(cursor).decode().split("|")
        return datetime.fromisoformat(created), UUID(row_id)
    except ValueError as error:
        raise ValidationFailedError({"cursor": "Invalid cursor"}) from error


def page_request(
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PageRequest:
    return PageRequest(limit, decode_cursor(cursor) if cursor else None)


PageParams = Annotated[PageRequest, Depends(page_request)]


def paginate(
    statement: Select,
    created: InstrumentedAttribute,
    row_id: InstrumentedAttribute,
    page: PageRequest,
) -> Select:
    """Order by creation time and fetch one row more than the page holds."""
    statement = statement.order_by(created, row_id).limit(page.limit + 1)
    if page.after is None:
        return statement
    after_created, after_id = page.after
    return statement.where(
        or_(
            created > after_created,
            and_(created == after_created, row_id > after_id),
        )
    )


def build_page(
    rows: list[Any],
    page: PageRequest,
    schema: type[BaseModel],
    created: str = "created",
) -> Page:
    items = rows[: page.limit]
    has_more = len(rows) > page.limit
    last = items[-1] if has_more else None
    return Page(
        items=[schema.model_validate(row) for row in items],
        next=encode_cursor(getattr(last, created), last.id) if has_more else None,
    )
