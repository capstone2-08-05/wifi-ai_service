"""Inference 라우트에서 발생한 예외를 AppError로 정규화."""

from __future__ import annotations

from app.api.errors import AppError, ErrorCode


def normalize_inference_exception(exc: Exception, *, model: str, file_id: str) -> AppError:
    phase = f"inference_{model.lower()}"
    context = {"model": model, "file_id": file_id}

    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, FileNotFoundError):
        return AppError(
            status_code=404,
            detail=str(exc),
            code=ErrorCode.INFERENCE_RESOURCE_NOT_FOUND,
            layer="infrastructure",
            phase=f"{phase}_resource_load",
            retryable=False,
            context=context,
            cause=exc,
        )
    if isinstance(exc, ValueError):
        return AppError(
            status_code=400,
            detail=str(exc),
            code=ErrorCode.INFERENCE_INVALID_INPUT,
            layer="usecase",
            phase=f"{phase}_validation",
            retryable=False,
            context=context,
            cause=exc,
        )
    return AppError(
        status_code=500,
        detail=f"{model} runtime failed: {exc}",
        code=ErrorCode.INFERENCE_RUNTIME_FAILED,
        layer="infrastructure",
        phase=f"{phase}_execute",
        retryable=False,
        context=context,
        cause=exc,
    )


__all__ = ["normalize_inference_exception"]
