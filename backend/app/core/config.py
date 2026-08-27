"""Environment-driven application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Chargeback Risk & Evidence Response Agent"
    app_env: Literal["development", "test", "production"] = "development"
    seed_demo_data: bool = False
    database_url: str = "sqlite:///./chargeback_risk.db"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 20
    gemini_max_retries: int = 1
    backend_cors_origins: str = "http://localhost:5173"
    ml_model_artifact_path: str = "artifacts/models/chargeback-risk-v1.joblib"
    risk_low_threshold: int = 35
    risk_high_threshold: int = 70

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Ensure the configured database URL is explicit and supported."""
        if not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        supported_prefixes = ("sqlite:///", "sqlite+pysqlite:///", "postgresql://", "postgresql+psycopg://")
        if not value.startswith(supported_prefixes):
            raise ValueError("DATABASE_URL must be a SQLite or PostgreSQL-compatible SQLAlchemy URL")
        return value

    @field_validator("risk_low_threshold", "risk_high_threshold")
    @classmethod
    def validate_risk_thresholds(cls, value: int) -> int:
        """Ensure risk thresholds can map scores on a 0-100 scale."""
        if not 0 <= value <= 100:
            raise ValueError("Risk thresholds must be between 0 and 100")
        return value

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        """Require an explicit non-empty Gemini model name."""
        if not value.strip():
            raise ValueError("GEMINI_MODEL must not be empty")
        return value.strip()

    @field_validator("gemini_timeout_seconds")
    @classmethod
    def validate_gemini_timeout(cls, value: int) -> int:
        """Keep external LLM calls bounded."""
        if not 1 <= value <= 120:
            raise ValueError("GEMINI_TIMEOUT_SECONDS must be between 1 and 120")
        return value

    @field_validator("gemini_max_retries")
    @classmethod
    def validate_gemini_retries(cls, value: int) -> int:
        """Keep Gemini retries bounded so failed investigations return promptly."""
        if not 0 <= value <= 3:
            raise ValueError("GEMINI_MAX_RETRIES must be between 0 and 3")
        return value

    @field_validator("backend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        """Require explicit HTTP(S) origins and prevent wildcard deployment CORS."""
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins:
            raise ValueError("BACKEND_CORS_ORIGINS must contain at least one origin")
        for origin in origins:
            if origin == "*":
                raise ValueError("BACKEND_CORS_ORIGINS must list explicit origins; wildcard CORS is not allowed")
            if not origin.startswith(("http://", "https://")):
                raise ValueError("BACKEND_CORS_ORIGINS entries must be absolute HTTP(S) origins")
        return ",".join(origins)

    def model_post_init(self, __context: object) -> None:
        """Validate relative ordering for score thresholds after field parsing."""
        if self.risk_low_threshold >= self.risk_high_threshold:
            raise ValueError("RISK_LOW_THRESHOLD must be lower than RISK_HIGH_THRESHOLD")

    @property
    def cors_origins(self) -> list[str]:
        """Return CORS origins as a normalized list."""
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached validated application settings."""
    return Settings()
