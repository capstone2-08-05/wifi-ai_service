"""내부 Sionna 실행 API (인증·DB 본연동 없음, sionna_rt 기본)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_sionna_runner
from app.api.errors import AppError, ErrorCode, to_http_exception
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto
from app.presentation.responses.sionna_response_dto import (
    SionnaRunResponseDto,
    to_sionna_response,
)
from app.usecases.run_sionna_usecase import run_sionna_usecase

router = APIRouter()

_ERROR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "detail": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "status": {"type": "integer"},
                        "layer": {"type": "string"},
                        "phase": {"type": "string"},
                        "retryable": {"type": "boolean"},
                        "context": {"type": "object"},
                    },
                    "required": ["code", "message", "status", "layer", "phase", "retryable", "context"],
                }
            },
            "required": ["error"],
        }
    },
    "required": ["detail"],
}

_SIONNA_ERROR_RESPONSES = {
    400: {
        "description": "Invalid Sionna request",
        "content": {
            "application/json": {
                "schema": _ERROR_RESPONSE_SCHEMA,
                "example": {
                    "detail": {
                        "error": {
                            "code": "SIONNA_INVALID_ENGINE",
                            "message": "only engine=sionna_rt is supported",
                            "status": 400,
                            "layer": "api",
                            "phase": "request_validate",
                            "retryable": False,
                            "context": {"engine": "legacy", "run_type": "run"},
                        }
                    }
                },
            }
        },
    },
    500: {
        "description": "Sionna runtime failure",
        "content": {
            "application/json": {
                "schema": _ERROR_RESPONSE_SCHEMA,
                "examples": {
                    "runtime_import_error": {
                        "summary": "Sionna runtime package is unavailable",
                        "value": {
                            "detail": {
                                "error": {
                                    "code": "EXTERNAL_RUNTIME_IMPORT_ERROR",
                                    "message": "ImportError: Sionna runtime is not available.",
                                    "status": 500,
                                    "layer": "infrastructure",
                                    "phase": "runtime_execute",
                                    "retryable": False,
                                    "context": {"engine": "sionna_rt", "run_type": "run", "floor_id": None},
                                }
                            }
                        },
                    },
                    "runtime_execute_error": {
                        "summary": "Sionna runtime execution failed",
                        "value": {
                            "detail": {
                                "error": {
                                    "code": "SIONNA_RUNTIME_FAILED",
                                    "message": "RuntimeError: CUDA out of memory",
                                    "status": 500,
                                    "layer": "infrastructure",
                                    "phase": "runtime_execute",
                                    "retryable": False,
                                    "context": {"engine": "sionna_rt", "run_type": "run", "floor_id": "f1"},
                                }
                            }
                        },
                    },
                },
            }
        },
    },
}


@router.post(
    "/sionna/run",
    response_model=SionnaRunResponseDto,
    responses=_SIONNA_ERROR_RESPONSES,
)
def post_internal_sionna_run(
    body: SionnaRunRequestDto,
    runner=Depends(get_sionna_runner),
) -> SionnaRunResponseDto:
    try:
        if body.engine != "sionna_rt":
            raise AppError(
                status_code=400,
                detail="only engine=sionna_rt is supported",
                code=ErrorCode.SIONNA_INVALID_ENGINE,
                layer="api",
                phase="request_validate",
                context={"engine": body.engine, "run_type": body.run_type},
            )
        result = run_sionna_usecase(body, runner)
        if result.get("status") == "failed":
            raw_error = str(result.get("error") or "Sionna RT run failed")
            lowered = raw_error.lower()
            code = (
                ErrorCode.EXTERNAL_RUNTIME_IMPORT_ERROR
                if "importerror" in lowered
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
    except Exception as exc:
        raise to_http_exception(exc) from exc
    return to_sionna_response(result)
