from importlib import metadata
from pathlib import Path

REQUIREMENTS = Path(__file__).parents[1] / "requirements.txt"
GEMINI = "gemini-geothermal-suite-open"
GEMINI_VERSION = "0.5.14"
GEOMIND_VERSION = "0.4.19"
DIGEST_LENGTH = 64


def requirement_lines() -> list[str]:
    return REQUIREMENTS.read_text().splitlines()


def gemini_line() -> str:
    lines = [line for line in requirement_lines() if line.startswith(f"{GEMINI} @ ")]
    assert len(lines) == 1, f"{GEMINI} is not pinned to one wheel"
    return lines[0]


def test_gemini_is_the_released_wheel_pinned() -> None:
    assert f"/v{GEMINI_VERSION}/" in gemini_line()
    wheel, _, digest = gemini_line().partition("#sha256=")
    assert wheel.endswith(f"-{GEMINI_VERSION}-py3-none-any.whl")
    assert len(digest) == DIGEST_LENGTH
    assert metadata.version(GEMINI) == GEMINI_VERSION


def test_nothing_is_installed_editable() -> None:
    assert not [line for line in requirement_lines() if line.startswith("-e")]


def test_geomind_is_the_released_wheel_pinned() -> None:
    lines = [line for line in requirement_lines() if line.startswith("geomind @ ")]
    assert len(lines) == 1, "geomind is not pinned to one wheel"
    wheel, _, digest = lines[0].partition("#sha256=")
    assert f"/v{GEOMIND_VERSION}/" in wheel
    assert wheel.endswith(f"geomind-{GEOMIND_VERSION}-py3-none-any.whl")
    assert len(digest) == DIGEST_LENGTH
    assert metadata.version("geomind") == GEOMIND_VERSION
