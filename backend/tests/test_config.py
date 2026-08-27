"""Tests for validated environment configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parses_cors_origins() -> None:
    """Comma-separated CORS origins should normalize into a list."""
    settings = Settings(backend_cors_origins="http://localhost:5173, https://example.test")

    assert settings.cors_origins == ["http://localhost:5173", "https://example.test"]


def test_invalid_database_url_fails_clearly() -> None:
    """Unsupported database URLs should raise a clear validation error."""
    with pytest.raises(ValidationError, match="DATABASE_URL must be a SQLite or PostgreSQL-compatible"):
        Settings(database_url="mysql://example")


def test_empty_cors_origins_fail_clearly() -> None:
    """Empty CORS configuration should fail during startup settings validation."""
    with pytest.raises(ValidationError, match="BACKEND_CORS_ORIGINS must contain at least one origin"):
        Settings(backend_cors_origins=" , ")
