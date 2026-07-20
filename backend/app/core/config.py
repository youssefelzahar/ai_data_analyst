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

    # --- Authentication / JWT settings ---
    # Signing key for JWTs. Defaults to secret_key when left empty.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Bootstrap admin + company seeded on first startup (idempotent).
    bootstrap_company_name: str = "Default Company"
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123"

    # Bootstrap superadmin (platform owner) seeded on first startup (idempotent).
    # The superadmin's only capability is creating admins.
    bootstrap_superadmin_username: str = "youssefelzahar"
    bootstrap_superadmin_password: str = "123456"
    bootstrap_superadmin_company: str = "ai_analysis"

    upload_directory: str = "./uploaded_files"
    max_upload_size_mb: int = 200

    # --- AI / LLM settings ---
    ai_provider: str = "ollama"
    ai_default_model: str = "qwen3:4b"
    ai_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    ai_request_timeout_seconds: int = Field(default=300, ge=1, le=900)
    ollama_base_url: str = "http://localhost:11434"

    @property
    def effective_jwt_secret_key(self) -> str:
        """The key used to sign JWTs, falling back to secret_key when unset."""
        return self.jwt_secret_key or self.secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()

