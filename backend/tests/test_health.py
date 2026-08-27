"""Tests for the Phase 0 health endpoint."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok() -> None:
    """The health endpoint should prove the API is alive."""
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
