import logging
from enum import StrEnum
from typing import Any

from fastapi import HTTPException


logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    INFERENCE_RESOURCE_NOT_FOUND = "INFERENCE_RESOURCE_NOT_FOUND"
    INFERENCE_INVALID_INPUT = "INFERENCE_INVALID_INPUT"
    INFERENCE_RUNTIME_FAILED = "INFERENCE_RUNTIME_FAILED"
    EXTERNAL_RUNTIME_IMPORT_ERROR = "EXTERNAL_RUNTIME_IMPORT_ERROR"
    SIONNA_INVALID_ENGINE = "SIONNA_INVALID_ENGINE"
    SIONNA_RUNTIME_FAILED = "SIONNA_RUNTIME_FAILED"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        layer: str = "api",
        phase: str = "request",
        retryable: bool = False,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.layer = layer
        self.phase = phase
        self.retryable = retryable
        self.context = context or {}
        self.cause = cause
        super().__init__(detail)


def _error_payload(
    *,
    code: ErrorCode,
    message: str,
    status: int,
    layer: str,
    phase: str,
    retryable: bool,
    context: dict[str, Any] | None = None,
    cause: Exception | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "status": status,
            "layer": layer,
            "phase": phase,
            "retryable": retryable,
            "context": context or {},
        }
    }
    if cause is not None:
        payload["error"]["cause"] = {
            "type": type(cause).__name__,
            "detail": str(cause),
        }
    return payload


def to_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return exc
        return exc
    if isinstance(exc, AppError):
        return HTTPException(
            status_code=exc.status_code,
            detail=_error_payload(
                code=exc.code,
                message=exc.detail,
                status=exc.status_code,
                layer=exc.layer,
                phase=exc.phase,
                retryable=exc.retryable,
                context=exc.context,
                cause=exc.cause,
            ),
        )
    if isinstance(exc, FileNotFoundError):
        return HTTPException(
            status_code=404,
            detail=_error_payload(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=str(exc),
                status=404,
                layer="infrastructure",
                phase="resource_load",
                retryable=False,
                cause=exc,
            ),
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=400,
            detail=_error_payload(
                code=ErrorCode.INVALID_REQUEST,
                message=str(exc),
                status=400,
                layer="usecase",
                phase="validation",
                retryable=False,
                cause=exc,
            ),
        )
    logger.exception("Unhandled exception during API request")
    return HTTPException(
        status_code=500,
        detail=_error_payload(
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="Internal Server Error",
            status=500,
            layer="api",
            phase="unhandled",
            retryable=False,
            cause=exc,
        ),
    )
