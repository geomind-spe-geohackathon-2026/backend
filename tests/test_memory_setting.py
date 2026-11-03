from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SETTING = "MALLOC_ARENA_MAX=2"


def test_the_image_limits_malloc_arenas() -> None:
    assert f"ENV {SETTING}" in (ROOT / "Dockerfile").read_text().splitlines()


@pytest.mark.parametrize("name", [".env.example", ".env.dev.example"])
def test_example_env_files_limit_malloc_arenas(name: str) -> None:
    assert SETTING in (ROOT / name).read_text().splitlines()
