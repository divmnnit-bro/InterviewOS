from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or a .env file."""

    PROJECT_NAME: str = "InterviewOS"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/interviewos"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Auth. SECRET_KEY signs JWTs; it must be overridden outside development.
    SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Browser origins allowed to call the API, comma-separated (the frontend's address).
    # Leave empty to disable CORS. The API uses a bearer token, not cookies.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Upper bounds for solver options a client may request.
    SCHEDULER_MAX_TIME_LIMIT_SECONDS: float = 60.0
    SCHEDULER_MAX_WORKERS: int = 8

    # Redis for background jobs and caching
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Recruitment Copilot
    AI_PROVIDER: str = "deterministic"  # Supported providers: "deterministic" and "openai"
    AI_MODEL: str = "gpt-4o-mini"
    AI_API_KEY: str | None = None
    AI_API_BASE: str | None = None
    AI_REQUEST_TIMEOUT_SECONDS: float = 30.0

    # Optional SMTP delivery. No email is queued unless a host and sender are configured.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_USE_SSL: bool = False
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT_SECONDS: float = 10.0

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 120

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def email_delivery_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM)

    @model_validator(mode="after")
    def _require_real_secret_outside_dev(self) -> "Settings":
        if self.ENVIRONMENT != "development" and (
            self.SECRET_KEY.startswith("dev-only") or len(self.SECRET_KEY) < 32
        ):
            raise ValueError(
                "SECRET_KEY must be set to a random value of at least 32 characters "
                "when ENVIRONMENT is not 'development'"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
