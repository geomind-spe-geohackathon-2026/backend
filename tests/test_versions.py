from importlib import metadata
from pathlib import Path

REQUIREMENTS = Path(__file__).parents[1] / "requirements.txt"
GEMINI = "gemini-geothermal-suite-open"
GEMINI_VERSION = "0.5.5"
GEOMIND_NEEDED = (0, 4, 1)
DIGEST_LENGTH = 64


def requirement_lines() -> list[str]:
    return REQUIREMENTS.read_text().splitlines()


def gemini_line() -> str:
    lines = [line for line in requirement_lines() if line.startswith(f"{GEMINI} @ ")]
    assert len(lines) == 1, f"{GEMINI} is not pinned to one wheel"
    return lines[0]


def parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".")[:3])


def test_gemini_is_the_released_wheel_pinned() -> None:
    assert f"/v{GEMINI_VERSION}/" in gemini_line()
    wheel, _, digest = gemini_line().partition("#sha256=")
    assert wheel.endswith(f"-{GEMINI_VERSION}-py3-none-any.whl")
    assert len(digest) == DIGEST_LENGTH
    assert metadata.version(GEMINI) == GEMINI_VERSION


def test_only_geomind_is_still_editable_until_it_has_a_release() -> None:
    editable = [line for line in requirement_lines() if line.startswith("-e")]

    assert editable == ["-e ../geomind"]


def test_geomind_is_the_version_the_app_needs() -> None:
    assert parts(metadata.version("geomind")) >= GEOMIND_NEEDED
