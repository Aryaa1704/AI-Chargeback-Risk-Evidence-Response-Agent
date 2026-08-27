"""Consistent API error response helpers."""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"detail": "Not found", "code": "not_found"}]})
    detail: str
    code: str


def error_response(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ErrorResponse(detail=detail, code=code).model_dump())


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return error_response(exc.status_code, detail, "http_error")

    @app.exception_handler(HTTPException)
    async def fastapi_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return error_response(exc.status_code, detail, "http_error")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "Request validation failed", "validation_error")
