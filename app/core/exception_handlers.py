from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if value:
        return str(value)
    return uuid4().hex


def _response(
    *,
    request_id: str,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        },
        headers=response_headers,
    )


def _validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "loc": error.get("loc", ()),
            "message": error.get("msg", "Invalid input."),
            "type": error.get("type", "validation_error"),
        }
        for error in errors
    ]


def install_exception_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        detail = exc.detail
        if isinstance(detail, str):
            message = detail
            details = None
        else:
            message = "Request failed."
            details = detail
        return _response(
            request_id=request_id,
            status_code=exc.status_code,
            code="http_error",
            message=message,
            details=details,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            request_id=_request_id(request),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="validation_error",
            message="Request validation failed.",
            details=_validation_details(exc.errors()),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning(
            "Database integrity conflict",
            extra={
                "request_id": _request_id(request),
                "error_type": exc.__class__.__name__,
            },
        )
        return _response(
            request_id=_request_id(request),
            status_code=status.HTTP_409_CONFLICT,
            code="conflict",
            message="Request conflicts with existing data.",
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database operation failed")
        return _response(
            request_id=_request_id(request),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="database_error",
            message="Database service is unavailable.",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        message = str(exc)
        if isinstance(exc, RuntimeError) and "SEASONA_DATABASE_URL" in message:
            logger.warning("Database is not configured")
            return _response(
                request_id=_request_id(request),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="database_error",
                message="Database service is not configured.",
            )

        logger.exception("Unhandled application error")
        return _response(
            request_id=_request_id(request),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Internal server error.",
        )
