from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from src.core.errors import ValidationFailedError
from src.core.pagination.page import (
    PageRequest,
    build_page,
    decode_cursor,
    encode_cursor,
)


class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: object


def rows(count: int) -> list[SimpleNamespace]:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    return [SimpleNamespace(id=uuid4(), created=created) for _ in range(count)]


def test_cursor_round_trip() -> None:
    created, row_id = datetime(2026, 1, 1, tzinfo=UTC), uuid4()

    assert decode_cursor(encode_cursor(created, row_id)) == (created, row_id)


@pytest.mark.parametrize("cursor", ["not-a-cursor", "aGVsbG8=", "é"])
def test_bad_cursor_is_a_validation_error(cursor: str) -> None:
    with pytest.raises(ValidationFailedError) as error:
        decode_cursor(cursor)

    assert error.value.details == {"fields": {"cursor": "Invalid cursor"}}


def test_last_page_has_no_next_cursor() -> None:
    page = build_page(rows(2), PageRequest(limit=2), Item)

    assert len(page.items) == 2
    assert page.next is None


def test_full_page_points_at_its_last_row() -> None:
    fetched = rows(3)

    page = build_page(fetched, PageRequest(limit=2), Item)

    assert len(page.items) == 2
    assert decode_cursor(page.next)[1] == fetched[1].id
