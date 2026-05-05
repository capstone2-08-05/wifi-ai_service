"""Inference 라우트의 OpenAPI 에러 응답 정의."""

from __future__ import annotations

from app.api.error_responses import error_response, make_error_example


def _build(model: str) -> dict[int, dict]:
    model_lower = model.lower()
    context = {"model": model_lower, "file_id": "abc123"}
    return {
        400: error_response(
            description="Invalid inference request",
            example=make_error_example(
                code="INFERENCE_INVALID_INPUT",
                message="Failed to decode uploaded image bytes",
                status=400,
                layer="usecase",
                phase=f"inference_{model_lower}_validation",
                context=context,
            ),
        ),
        404: error_response(
            description="Inference resource not found",
            example=make_error_example(
                code="INFERENCE_RESOURCE_NOT_FOUND",
                message="YOLO config not found: /path/to/yolo_inference.yaml",
                status=404,
                layer="infrastructure",
                phase=f"inference_{model_lower}_resource_load",
                context=context,
            ),
        ),
        500: error_response(
            description="Inference runtime failure",
            example=make_error_example(
                code="INFERENCE_RUNTIME_FAILED",
                message=f"{model} runtime failed: RuntimeError: model load failed",
                status=500,
                layer="infrastructure",
                phase=f"inference_{model_lower}_execute",
                context=context,
            ),
        ),
    }


UNET_ERROR_RESPONSES = _build("unet")
YOLO_ERROR_RESPONSES = _build("yolo")

__all__ = ["UNET_ERROR_RESPONSES", "YOLO_ERROR_RESPONSES"]
