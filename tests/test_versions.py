from importlib import metadata
from pathlib import Path

REQUIREMENTS = Path(__file__).parents[1] / "requirements.txt"
ENGINES = ("gemini-geothermal-suite-open", "geomind")


def requirement_lines() -> list[str]:
    return REQUIREMENTS.read_text().splitlines()


def pin_of(package: str) -> str:
    prefix = f"{package}=="
    pins = [line for line in requirement_lines() if line.startswith(prefix)]
    assert len(pins) == 1, f"{package} is not pinned to one version"
    return pins[0].removeprefix(prefix)


def test_nothing_is_installed_in_editable_mode() -> None:
    assert not [line for line in requirement_lines() if line.startswith("-e")]


def test_the_engines_are_the_versions_pinned() -> None:
    for package in ENGINES:
        assert metadata.version(package) == pin_of(package)
