from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Data Analyst"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"

    # JSON list in env, e.g. CORS_ORIGINS=["http://localhost:3000"]
    cors_origins: list[str] = ["http://localhost:3000"]

    # Application metadata store (data source registry, not user data).
    # SQLite by default for local development; PostgreSQL in Docker/production.
    database_url: str = "sqlite:///./ai_data_analyst.db"

    # Symmetric key used to encrypt stored data source credentials.
    secret_key: str = "change-me-in-production"

    upload_directory: str = "./uploaded_files"
    max_upload_size_mb: int = 200

    # --- AI / LLM settings ---
    ai_provider: str = "ollama"
    ai_default_model: str = " qwen3:4b"
    ai_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    ai_request_timeout_seconds: int = Field(default=120, ge=1, le=600)
    ollama_base_url: str = "http://localhost:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
