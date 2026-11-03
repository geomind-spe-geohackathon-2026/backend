import pytest

from src.core.assistant.context import context_window


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("128000", 128000), ("", None), ("0", None), ("-5", None), ("lots", None)],
)
def test_the_window_is_a_positive_number_or_none(monkeypatch, raw, expected) -> None:
    monkeypatch.setenv("GEOMIND_CONTEXT_WINDOW", raw)
    assert context_window() == expected
