"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.seed.scaffold import seed_synthetic_demo_data

logger = logging.getLogger("app.request")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID and emit structured request logs without secrets."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-correlation-id"] = correlation_id
        logger.info(
            "request_completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    settings = get_settings()

    if settings.seed_demo_data:
        db = SessionLocal()
        try:
            counts = seed_synthetic_demo_data(db)
            logger.info("Demo seed completed: %s", counts)
        finally:
            db.close()

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
