"""Map exceptions to the shared error envelope (CONTRACTS.md#error-envelope)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.store.base import (
    IllegalTransition,
    RunCorrupt,
    RunNotFound,
    StoreUnavailable,
)

logger = logging.getLogger(__name__)

HTTP_CODES = {404: "NOT_FOUND"}


def error_response(
    status: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(
                    str(p) for p in e["loc"] if p not in ("body", "query", "path")
                ),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        first = errors[0] if errors else {"field": "", "message": "Invalid request"}
        label = first["field"] or "request"
        return error_response(
            422,
            "VALIDATION_ERROR",
            f"Invalid {label}: {first['message']}",
            {"errors": errors},
        )

    @app.exception_handler(RunNotFound)
    async def run_not_found(request: Request, exc: RunNotFound):
        return error_response(404, "RUN_NOT_FOUND", str(exc), {"run_id": exc.run_id})

    @app.exception_handler(IllegalTransition)
    async def illegal_transition(request: Request, exc: IllegalTransition):
        return error_response(
            409,
            "ILLEGAL_TRANSITION",
            str(exc),
            {"from": exc.from_.value, "to": exc.to.value},
        )

    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(request: Request, exc: StoreUnavailable):
        logger.error("Run store unavailable: %s", exc)
        return error_response(502, "UPSTREAM_ERROR", "The run store is unavailable")

    @app.exception_handler(RunCorrupt)
    async def run_corrupt(request: Request, exc: RunCorrupt):
        logger.error("%s", exc)
        return error_response(500, "INTERNAL_ERROR", "An internal error occurred")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code >= 500:
            code = "INTERNAL_ERROR"
        else:
            code = HTTP_CODES.get(exc.status_code, "BAD_REQUEST")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "INTERNAL_ERROR", "An internal error occurred")
