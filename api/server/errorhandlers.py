"""Central exception handlers for ContextIngest API.

Every error returned by the API uses one envelope:

    { "message": "human readable message" }

Unhandled exceptions are logged and turned into a generic 500 — never a stack
trace in the response body.
"""

import json

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from libs.logger import get_logger

logger = get_logger(__name__)


def make_json_safe(obj):
    """Recursively coerce a value into something `json.dumps` will accept."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    if isinstance(obj, dict):
        return {str(key): make_json_safe(value) for key, value in obj.items()}
    return str(obj)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        try:
            raw_errors = exc.errors()
            safe_errors = []

            for error in raw_errors:
                safe_error = {
                    "type": make_json_safe(error.get("type", "validation_error")),
                    "loc": make_json_safe(error.get("loc", [])),
                    "msg": make_json_safe(error.get("msg", "Validation error")),
                    "input": make_json_safe(error.get("input"))
                    if "input" in error
                    else None,
                }

                if "ctx" in error and error["ctx"]:
                    safe_error["ctx"] = make_json_safe(error["ctx"])

                safe_errors.append(safe_error)

            response_content = {
                "message": "Validation failed",
                "errors": safe_errors,
            }
            json.dumps(response_content)

            return JSONResponse(
                status_code=400,
                content=response_content,
            )
        except Exception as handling_error:
            logger.error("Error in validation error handler: %s", handling_error)
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Validation failed",
                    "errors": [{"msg": "Validation error occurred"}],
                },
            )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error("Unhandled exception on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"},
        )
