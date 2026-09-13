import math
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        case_sensitive=True,
    )

    DATABASE_URL: str = "postgresql+asyncpg://hydenlyne:hydenlyne_pass@db:5432/hydenlyne"
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_PASSWORD: str = ""
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    MEILI_HOST: str = "meilisearch"
    MEILI_PORT: int = 7700
    MEILI_MASTER_KEY: str = ""
    SENTRY_DSN: str = ""
    SESSION_SECRET_KEY: str = "dev_secret_key_change_in_production"
    SESSION_COOKIE_NAME: str = "hydenlyne_session"
    APP_ENV: str = "development"
    # Passwordless authentication is disabled unless a developer explicitly
    # opts into it for a deliberately isolated local environment.
    ALLOW_PASSWORDLESS_DEV_LOGIN: bool = False
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = ""
    CORS_ORIGINS: str = ""
    LOG_LEVEL: str = "INFO"
    DOCUMENT_STORAGE_PATH: str = "/app/data/documents"
    FLOWER_USER: str = "admin"
    FLOWER_PASSWORD: str = "flower_pass"
    DROPBOX_APP_KEY: str = ""
    DROPBOX_APP_SECRET: str = ""
    # Short-lived (``sl.``) token, ~4h.  Used only when no refresh
    # token is configured.
    DROPBOX_ACCESS_TOKEN: str = ""
    # Long-lived credential from a ``token_access_type=offline``
    # authorisation.  When set, access tokens are minted on demand.
    DROPBOX_REFRESH_TOKEN: str = ""
    DROPBOX_WEBHOOK_SECRET: str = ""
    # When enabled, a document upload succeeds only after Dropbox confirms
    # receipt.  The local cache remains a mirror, never the sole copy.
    REQUIRE_DROPBOX_STORAGE: bool = False
    API_KEY: str = ""
    OLLAMA_EXTRACTION_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    OLLAMA_VISION_MODEL: str = "llama3.2-11b-vision-instruct-q4_K_M"
    OLLAMA_EMBEDDING_MODEL: str = "all-minilm"
    # Off by default: Qdrant indexing/semantic search is validated but not yet
    # wired into the default write/read path. See backend/docs/consultant-knowledge-core.md.
    ENABLE_SEMANTIC_SEARCH: bool = False
    SESSION_MAX_AGE: int = 28800
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    # VesselAPI (https://github.com/vessel-api) — real-time AIS proxy.
    # Leave blank to disable external vessel search; backend then returns a
    # typed unavailable signal instead of failing open to the provider.
    VESSELAPI_API_KEY: str = ""
    VESSELAPI_BASE_URL: str = "https://api.vesselapi.com/v1"
    VESSELAPI_TIMEOUT_SECONDS: float = 10.0
    VESSELAPI_CACHE_TTL_SECONDS: int = 120

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> str:
        """Normalize and constrain the environment security mode."""
        normalized = str(value).strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        return normalized

    @field_validator("SESSION_MAX_AGE", "VESSELAPI_CACHE_TTL_SECONDS")
    @classmethod
    def validate_positive_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be greater than zero")
        return value

    @field_validator("VESSELAPI_TIMEOUT_SECONDS")
    @classmethod
    def validate_vessel_api_timeout(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("VESSELAPI_TIMEOUT_SECONDS must be finite and greater than zero")
        return value


def validate_prod_secrets(settings: Settings | None = None) -> None:
    """Fail fast when a production process still uses development secrets."""
    current = settings or get_settings()
    if current.APP_ENV != "production":
        return
    insecure_defaults = {
        "SESSION_SECRET_KEY": "dev_secret_key_change_in_production",  # nosec B105
        "MEILI_MASTER_KEY": "meili_master_key_change_in_production",  # nosec B105
        "REDIS_PASSWORD": "",  # nosec B105
        "FLOWER_PASSWORD": "flower_pass",  # nosec B105
        "ADMIN_PASSWORD": "",  # nosec B105
    }
    known_dev_values = {
        "dev_redis_pass",
        "hydenlyne_pass",
        "flower_pass",
        "set_a_long_random_value_for_prod",
        "change_this_to_a_random_secret_key_at_least_32_chars",
    }
    for key, bad_default in insecure_defaults.items():
        val = getattr(current, key, "")
        if not val or val == bad_default or val in known_dev_values:
            raise RuntimeError(
                f"Refusing to start in production: {key} is unset or still default. "
                "Set a strong random value via env/secret manager."
            )
    if "hydenlyne_pass" in current.DATABASE_URL:
        raise RuntimeError(
            "Refusing to start in production: DATABASE_URL still uses the "
            "compose dev password. Set POSTGRES_PASSWORD explicitly."
        )
    if current.SESSION_SECRET_KEY and len(current.SESSION_SECRET_KEY) < 32:
        raise RuntimeError("SESSION_SECRET_KEY must be >=32 chars in production")
    if "sqlite" in current.DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be PostgreSQL in production, not sqlite")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
