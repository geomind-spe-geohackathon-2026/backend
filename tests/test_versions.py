from hashlib import sha256
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
VENDOR = ROOT / "vendor"
GEMINI = "gemini-geothermal-suite-open"
GEMINI_VERSION = "0.5.5"
GEOMIND_VERSION = "0.4.4"
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


def test_geomind_is_the_released_wheel_with_its_hash() -> None:
    wheel = f"geomind-{GEOMIND_VERSION}-py3-none-any.whl"
    assert f"./vendor/{wheel}" in requirement_lines()
    digest = sha256((VENDOR / wheel).read_bytes()).hexdigest()
    assert f"{digest}  {wheel}" in (VENDOR / "SHA256SUMS").read_text().splitlines()
    assert metadata.version("geomind") == GEOMIND_VERSION
