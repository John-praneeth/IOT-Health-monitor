"""
exception_handlers.py  –  Global exception handlers for FastAPI.
Returns standardized JSON error responses.
Does NOT expose internal errors in production.
"""

import os
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from logger import log_security_event

logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"


def setup_exception_handlers(app: FastAPI):
    """Register global exception handlers on the app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == 403:
            log_security_event(
                "FORBIDDEN_ACCESS",
                request=request,
                path=request.url.path,
                method=request.method,
            )
        logger.warning(
            "HTTP %d: %s %s – %s",
            exc.status_code, request.method, request.url.path, exc.detail,
            extra={"action": "http_error"},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.status_code,
                    "message": exc.detail,
                    "type": "HTTPException",
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        safe_errors = []
        for err in exc.errors():
            safe_err = err.copy()
            safe_err.pop('input', None)
            safe_err.pop('url', None)
            
            # Fix: Ensure 'ctx' contains only serializable data (convert ValueError etc to string)
            if 'ctx' in safe_err and isinstance(safe_err['ctx'], dict):
                for k, v in safe_err['ctx'].items():
                    if isinstance(v, Exception):
                        safe_err['ctx'][k] = str(v)
            
            safe_errors.append(safe_err)
            
        logger.warning(
            "Validation error: %s %s – %s",
            request.method, request.url.path, str(safe_errors)[:500],
            extra={"action": "validation_error"},
        )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Validation error",
                    "type": "ValidationError",
                    "details": safe_errors if not IS_PRODUCTION else "Invalid request data",
                },
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(
            "Database error: %s %s – %s",
            request.method, request.url.path, str(exc),
            exc_info=True,
            extra={"action": "database_error"},
        )
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": 503,
                    "message": "A database error occurred. Please try again later.",
                    "type": "DatabaseError",
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Log the full stack trace
        logger.error(
            "Unhandled exception: %s %s – %s",
            request.method, request.url.path, str(exc),
            exc_info=True,
            extra={"action": "unhandled_error"},
        )

        # Try Sentry capture if available
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except ImportError:
            pass

        # Don't expose internals in production
        detail = str(exc) if not IS_PRODUCTION else "An internal error occurred"
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": 500,
                    "message": detail,
                    "type": "InternalServerError",
                },
            },
        )
