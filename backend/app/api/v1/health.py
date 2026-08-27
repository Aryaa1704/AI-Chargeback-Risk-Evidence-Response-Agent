"""Health-check endpoint for service readiness checks."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response returned when the backend is alive."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "ok", "service": "api"}]})

    status: Literal["ok"]
    service: Literal["api"]


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return a small JSON message proving the backend is running."""
    return HealthResponse(status="ok", service="api")
