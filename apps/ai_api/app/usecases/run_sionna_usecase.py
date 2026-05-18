from __future__ import annotations

from typing import Any, Callable

from app.api.errors import AppError, ErrorCode
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto


SionnaRunner = Callable[[SionnaRunRequestDto], dict[str, Any]]


def run_sionna_usecase(body: SionnaRunRequestDto, runner: SionnaRunner) -> dict[str, Any]:
    if body.engine != "sionna_rt":
        raise AppError(
            status_code=400,
            detail="only engine=sionna_rt is supported",
            code=ErrorCode.SIONNA_INVALID_ENGINE,
            layer="api",
            phase="request_validate",
            context={"engine": body.engine, "run_type": body.run_type},
        )

    result = runner(body)

    if result.get("status") == "failed":
        raw_error = str(result.get("error") or "Sionna RT run failed")
        code = (
            ErrorCode.EXTERNAL_RUNTIME_IMPORT_ERROR
            if "importerror" in raw_error.lower()
            else ErrorCode.SIONNA_RUNTIME_FAILED
        )
        raise AppError(
            status_code=500,
            detail=raw_error,
            code=code,
            layer="infrastructure",
            phase="runtime_execute",
            retryable=False,
            context={
                "engine": body.engine,
                "run_type": body.run_type,
                "floor_id": body.floor_id,
            },
        )

    return result
