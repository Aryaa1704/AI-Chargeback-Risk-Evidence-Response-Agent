"""Tests for consistent API error formatting."""

from fastapi.testclient import TestClient

from app.main import app


def test_not_found_uses_consistent_error_format() -> None:
    """Unknown routes should use the project-wide error contract."""
    client = TestClient(app)

    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "http_error"}
