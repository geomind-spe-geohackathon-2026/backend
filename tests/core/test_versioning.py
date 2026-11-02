from types import SimpleNamespace

import pytest

from src.core.errors import ConflictError, NotFoundError
from src.core.versioning import check_base, latest_version


def test_base_equal_to_latest_passes() -> None:
    check_base(SimpleNamespace(number=3), 3)
    check_base(None, None)


@pytest.mark.parametrize(("latest", "base"), [(3, 2), (3, None), (None, 1)])
def test_other_base_is_conflict_with_the_latest_number(latest, base) -> None:
    row = SimpleNamespace(number=latest) if latest else None

    with pytest.raises(ConflictError) as error:
        check_base(row, base)

    assert error.value.details == {"latest": latest}


async def test_latest_version_raises_the_given_error_when_none() -> None:
    class Empty:
        async def latest_version(self, _project_id):
            return None

    with pytest.raises(NotFoundError):
        await latest_version(Empty(), "p", NotFoundError)
