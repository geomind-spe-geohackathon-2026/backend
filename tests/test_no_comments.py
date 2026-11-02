"""Code holds docstrings and tool directives, never comments."""

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("src", "tests")
DIRECTIVE = re.compile(
    r"#\s*(noqa|type:\s*ignore|pragma:|fmt:\s*(off|on|skip)|ruff:|pyright:|mypy:)"
)


def comments(source: str) -> list[tuple[int, str]]:
    """Return the line and text of every comment that is not a tool directive."""
    found = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and not DIRECTIVE.match(token.string):
            found.append((token.start[0], token.string))
    return found


def violations(root: Path) -> list[str]:
    found = []
    for folder in FOLDERS:
        for file in sorted((root / folder).rglob("*.py")):
            for line, text in comments(file.read_text()):
                found.append(f"{file.relative_to(root)}:{line}: {text}")
    return found


def test_code_has_no_comments() -> None:
    assert violations(ROOT) == []


def test_a_comment_is_found() -> None:
    assert comments("x = 1  # why\n") == [(1, "# why")]


def test_a_hash_inside_a_string_is_not_a_comment() -> None:
    assert comments('x = "a # b"\n') == []


def test_tool_directives_are_allowed() -> None:
    assert comments("import x  # noqa: F401\ny = z  # type: ignore[attr]\n") == []


def test_docstrings_are_allowed() -> None:
    assert comments('def f():\n    """Say # nothing."""\n') == []
