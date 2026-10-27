from unittest.mock import MagicMock

import pytest

from src import celery, fastapi, main


@pytest.mark.parametrize(
    ("argument", "fastapi_calls", "celery_calls"),
    [("--fastapi", 1, 0), ("--celery", 0, 1)],
)
def test_main_runs_selected_service(
    monkeypatch,
    argument: str,
    fastapi_calls: int,
    celery_calls: int,
) -> None:
    run_fastapi = MagicMock()
    run_celery = MagicMock()
    monkeypatch.setattr(fastapi, "run", run_fastapi)
    monkeypatch.setattr(celery, "run", run_celery)
    monkeypatch.setattr("sys.argv", ["main", argument])

    main.main()

    assert run_fastapi.call_count == fastapi_calls
    assert run_celery.call_count == celery_calls
