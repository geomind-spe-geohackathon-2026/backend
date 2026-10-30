from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.settings import FIRST_ADMIN_PASSWORD_PLACEHOLDER, Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
STRONG_PASSWORD = "a-long-enough-password"


def settings_with(app_env: str, password: str) -> Settings:
    return Settings(
        _env_file=None,
        JWT_SECRET_KEY="test-secret",
        APP_ENV=app_env,
        FIRST_ADMIN_PASSWORD=password,
    )


def test_placeholder_is_the_value_in_env_example() -> None:
    expected = f"FIRST_ADMIN_PASSWORD={FIRST_ADMIN_PASSWORD_PLACEHOLDER}"

    assert expected in ENV_EXAMPLE.read_text().splitlines()


@pytest.mark.parametrize("app_env", ["test", "production"])
def test_placeholder_is_refused_outside_development(app_env: str) -> None:
    with pytest.raises(ValidationError, match=".env.example"):
        settings_with(app_env, FIRST_ADMIN_PASSWORD_PLACEHOLDER)


def test_short_password_is_refused_outside_development() -> None:
    with pytest.raises(ValidationError, match="at least 12 characters"):
        settings_with("production", "elevenchars")


def test_error_does_not_print_the_password() -> None:
    with pytest.raises(ValidationError) as error:
        settings_with("production", "elevenchars")

    assert "elevenchars" not in str(error.value)
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize(
    ("app_env", "password"),
    [
        ("production", STRONG_PASSWORD),
        ("production", ""),
        ("development", FIRST_ADMIN_PASSWORD_PLACEHOLDER),
        ("development", "short"),
    ],
)
def test_allowed_passwords_load(app_env: str, password: str) -> None:
    assert settings_with(app_env, password).FIRST_ADMIN_PASSWORD == password
