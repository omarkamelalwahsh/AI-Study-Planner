from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Production-grade settings:
    - Reads from environment variables (+ .env for local dev)
    - Fails fast in production if DATABASE_URL is missing
    - No hardcoded credentials
    """

    # App
    APP_ENV: str = "dev"  # dev | staging | prod
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001

    # Database (REQUIRED in prod)
    DATABASE_URL: Optional[str] = None

    # LLM
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""  # must be set via env/.env
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Embeddings
    EMBED_MODEL_NAME: str = "intfloat/multilingual-e5-small"

    # Data directories
    DATA_DIR: str = "data"

    # Feature flags
    ENABLE_MEMORY: bool = True
    ENABLE_PDF: bool = True
    USE_RERANKER: bool = False

    # Load env vars, and for local dev also load `.env`
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("APP_ENV")
    @classmethod
    def normalize_env(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in {"dev", "staging", "prod"}:
            raise ValueError("APP_ENV must be one of: dev, staging, prod")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: Optional[str], info):
        # Fail-fast in production
        app_env = (info.data.get("APP_ENV") or "dev").strip().lower()

        if not v:
            if app_env == "prod":
                raise ValueError("DATABASE_URL is required in production (APP_ENV=prod).")
            return v

        # Basic sanity check (do not over-validate)
        v = v.strip()
        if not (v.startswith("postgresql://") or v.startswith("postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql:// or postgresql+psycopg2://).")

        return v


settings = Settings()
