from importlib import import_module
from unittest.mock import MagicMock

import pytest

from src import celery, fastapi, main
from src.api import TASK_MODULES


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


def test_celery_includes_every_task_module() -> None:
    assert celery.app.conf.include == TASK_MODULES
    assert TASK_MODULES
    for name in TASK_MODULES:
        assert name.endswith(".tasks")
        import_module(name)
