import logging
from enum import StrEnum
from typing import Any

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

