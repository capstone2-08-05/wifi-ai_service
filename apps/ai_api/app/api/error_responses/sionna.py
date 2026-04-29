"""Sionna 라우트의 OpenAPI 에러 응답 정의."""

from __future__ import annotations

from app.api.error_responses import error_response, make_error_example

SIONNA_ERROR_RESPONSES = {
    400: error_response(
        description="Invalid Sionna request",
        example=make_error_example(
            code="SIONNA_INVALID_ENGINE",
            message="only engine=sionna_rt is supported",
            status=400,
            layer="api",
            phase="request_validate",
            context={"engine": "legacy", "run_type": "run"},
        ),
    ),
    500: error_response(
        description="Sionna runtime failure",
        examples={
            "runtime_import_error": {
                "summary": "Sionna runtime package is unavailable",
                "value": make_error_example(
                    code="EXTERNAL_RUNTIME_IMPORT_ERROR",
                    message="ImportError: Sionna runtime is not available.",
                    status=500,
                    layer="infrastructure",
                    phase="runtime_execute",
                    context={"engine": "sionna_rt", "run_type": "run", "floor_id": None},
                ),
            },
            "runtime_execute_error": {
                "summary": "Sionna runtime execution failed",
                "value": make_error_example(
                    code="SIONNA_RUNTIME_FAILED",
                    message="RuntimeError: CUDA out of memory",
                    status=500,
                    layer="infrastructure",
                    phase="runtime_execute",
                    context={"engine": "sionna_rt", "run_type": "run", "floor_id": "f1"},
                ),
            },
        },
    ),
}

__all__ = ["SIONNA_ERROR_RESPONSES"]
