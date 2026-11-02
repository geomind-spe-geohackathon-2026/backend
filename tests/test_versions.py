import gemini
import geomind

GEMINI_NEEDED = (0, 5, 2)
GEOMIND_NEEDED = (0, 4, 0)


def parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".")[:3])


def test_the_engines_are_the_versions_the_app_needs() -> None:
    assert parts(gemini.__version__) >= GEMINI_NEEDED
    assert parts(geomind.__version__) >= GEOMIND_NEEDED
