from fastapi import APIRouter, Depends

from app.api.deps import get_unet_runner, get_yolo_runner
from app.api.errors import AppError, ErrorCode, to_http_exception
from app.presentation.requests.inference_request_dto import (
    InferenceUploadRequestDto,
    parse_inference_upload_request,
)
from app.usecases.run_unet_usecase import run_unet_usecase
from app.usecases.run_yolo_usecase import run_yolo_usecase
from packages.contracts.inference import UnetInferenceResponse, YoloInferenceResponse

router = APIRouter(tags=["inference"])

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


def _inference_error_responses(model: str) -> dict[int, dict]:
    model_lower = model.lower()
    return {
        400: {
            "description": "Invalid inference request",
            "content": {
                "application/json": {
                    "schema": _ERROR_RESPONSE_SCHEMA,
                    "example": {
                        "detail": {
                            "error": {
                                "code": "INFERENCE_INVALID_INPUT",
                                "message": "Failed to decode uploaded image bytes",
                                "status": 400,
                                "layer": "usecase",
                                "phase": f"inference_{model_lower}_validation",
                                "retryable": False,
                                "context": {"model": model_lower, "file_id": "abc123"},
                            }
                        }
                    },
                }
            },
        },
        404: {
            "description": "Inference resource not found",
            "content": {
                "application/json": {
                    "schema": _ERROR_RESPONSE_SCHEMA,
                    "example": {
                        "detail": {
                            "error": {
                                "code": "INFERENCE_RESOURCE_NOT_FOUND",
                                "message": "YOLO config not found: /path/to/yolo_inference.yaml",
                                "status": 404,
                                "layer": "infrastructure",
                                "phase": f"inference_{model_lower}_resource_load",
                                "retryable": False,
                                "context": {"model": model_lower, "file_id": "abc123"},
                            }
                        }
                    },
                }
            },
        },
        500: {
            "description": "Inference runtime failure",
            "content": {
                "application/json": {
                    "schema": _ERROR_RESPONSE_SCHEMA,
                    "example": {
                        "detail": {
                            "error": {
                                "code": "INFERENCE_RUNTIME_FAILED",
                                "message": f"{model} runtime failed: RuntimeError: model load failed",
                                "status": 500,
                                "layer": "infrastructure",
                                "phase": f"inference_{model_lower}_execute",
                                "retryable": False,
                                "context": {"model": model_lower, "file_id": "abc123"},
                            }
                        }
                    },
                }
            },
        },
    }


def _normalize_inference_exception(exc: Exception, *, model: str, file_id: str) -> AppError:
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


@router.post(
    "/inference/unet",
    response_model=UnetInferenceResponse,
    responses=_inference_error_responses("unet"),
)
def inference_unet(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
    runner=Depends(get_unet_runner),
) -> UnetInferenceResponse:
    try:
        return run_unet_usecase(req, runner)
    except Exception as exc:
        raise to_http_exception(
            _normalize_inference_exception(exc, model="unet", file_id=req.file_id)
        ) from exc


@router.post(
    "/inference/yolo",
    response_model=YoloInferenceResponse,
    responses=_inference_error_responses("yolo"),
)
def inference_yolo(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
    runner=Depends(get_yolo_runner),
) -> YoloInferenceResponse:
    try:
        return run_yolo_usecase(req, runner)
    except Exception as exc:
        raise to_http_exception(
            _normalize_inference_exception(exc, model="yolo", file_id=req.file_id)
        ) from exc
