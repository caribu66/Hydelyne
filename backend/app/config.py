from functools import lru_cache
from pathlib import Path

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
