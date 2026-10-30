import re
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.errors import AppError

EXACT_ORIGIN = re.compile(r"https?://(\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?")
FIRST_ADMIN_PASSWORD_PLACEHOLDER = "replace-with-first-admin-password"
FIRST_ADMIN_PASSWORD_MIN_LENGTH = 12


class SettingsValidationError(AppError, ValueError):
    pass


class Settings(BaseSettings):
    APP_NAME: str = "swarmax-backend"
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_DEBUG: bool = False
    APP_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    APP_VERSION: str = "0.1.0"
    APP_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    FIRST_ADMIN_EMAIL: str = ""
    FIRST_ADMIN_PASSWORD: str = ""

    POSTGRES_URL: str = "postgresql+asyncpg://admin:replace-with-postgres-password@postgres:5432/swarmax"
    POSTGRES_POOL_SIZE: int = 5
    POSTGRES_MAX_OVERFLOW: int = 10

    REDIS_URL: str = "redis://default:replace-with-redis-password@redis:6379/0"
    CELERY_BROKER_URL: str = "redis://default:replace-with-redis-password@redis:6379/1"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    PROJECT_IMPORT_MAX_BYTES: int = 100_000_000

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "replace-with-minio-password"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "swarmax"

    CHROMADB_URL: str = "http://chromadb:8000"

    INFLUXDB_URL: str = "http://influxdb:8086"
    INFLUXDB_TOKEN: str = "replace-with-influxdb-token"
    INFLUXDB_ORG: str = "swarmax"
    INFLUXDB_BUCKET: str = "swarmax"

    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        for origin in self.APP_CORS_ORIGINS:
            if "*" in origin or not EXACT_ORIGIN.fullmatch(origin):
                raise SettingsValidationError(
                    "APP_CORS_ORIGINS entries must be exact HTTP or HTTPS origins"
                )
        return self

    @model_validator(mode="after")
    def validate_first_admin_password(self) -> "Settings":
        """Refuse a known or short admin password, except in development.

        An empty password stays allowed: it only means no admin is created.
        """
        password = self.FIRST_ADMIN_PASSWORD
        if self.APP_ENV == "development" or not password:
            return self
        if password == FIRST_ADMIN_PASSWORD_PLACEHOLDER:
            raise SettingsValidationError(
                "FIRST_ADMIN_PASSWORD still has the .env.example value; set a real one"
            )
        if len(password) < FIRST_ADMIN_PASSWORD_MIN_LENGTH:
            raise SettingsValidationError(
                "FIRST_ADMIN_PASSWORD must have at least "
                f"{FIRST_ADMIN_PASSWORD_MIN_LENGTH} characters"
            )
        return self


settings = Settings()
