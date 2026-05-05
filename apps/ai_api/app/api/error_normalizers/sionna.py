"""Sionna 라우트에서 발생한 예외를 AppError로 정규화."""

from __future__ import annotations

from app.api.errors import AppError, ErrorCode
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto


def normalize_sionna_exception(exc: Exception, *, body: SionnaRunRequestDto) -> AppError:
    if isinstance(exc, AppError):
        return exc
    return AppError(
        status_code=500,
        detail=f"Sionna runtime failed: {exc}",
        code=ErrorCode.SIONNA_RUNTIME_FAILED,
        layer="infrastructure",
        phase="runtime_execute",
        retryable=False,
        context={
            "engine": body.engine,
            "run_type": body.run_type,
            "floor_id": body.floor_id,
        },
        cause=exc,
    )


__all__ = ["normalize_sionna_exception"]
