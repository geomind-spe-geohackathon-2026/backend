from src.core.problems import problem_of, readable


def test_a_lower_bound_is_written_in_words() -> None:
    message = "site.depth: value = -1 m; expected within the bounds {'min': 0.0} (SI)"

    assert (
        readable(message) == "site.depth: value = -1 m; expected at least 0 in SI units"
    )


def test_an_upper_bound_is_written_in_words() -> None:
    assert readable("expected within the bounds {'max': 1.5} (SI)") == (
        "expected at most 1.5 in SI units"
    )


def test_both_bounds_are_written_in_words() -> None:
    assert readable("expected within the bounds {'min': 1.0, 'max': 3.0}") == (
        "expected between 1 and 3"
    )


def test_a_message_without_bounds_stays() -> None:
    assert readable("a value is missing") == "a value is missing"


def test_a_problem_carries_the_readable_message() -> None:
    raw = {
        "path": "a",
        "code": "out_of_bounds",
        "message": "expected within the bounds {'min': 0.0}",
    }

    assert problem_of(raw)["message"] == "expected at least 0"
