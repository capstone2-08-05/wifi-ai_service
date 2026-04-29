from fastapi import APIRouter, Depends

from app.api.deps import parse_inference_upload_request
from app.api.error_normalizers.inference import normalize_inference_exception
from app.api.error_responses.inference import UNET_ERROR_RESPONSES, YOLO_ERROR_RESPONSES
from app.infrastructure.ai_runtime.inference_runner import (
    run_unet_with_runtime,
    run_yolo_with_runtime,
)
from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from app.usecases.run_unet_usecase import run_unet_usecase
from app.usecases.run_yolo_usecase import run_yolo_usecase
from packages.contracts.inference import UnetInferenceResponse, YoloInferenceResponse

router = APIRouter(tags=["inference"])


@router.post(
    "/inference/unet",
    response_model=UnetInferenceResponse,
    responses=UNET_ERROR_RESPONSES,
)
def inference_unet(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
) -> UnetInferenceResponse:
    try:
        return run_unet_usecase(req, run_unet_with_runtime)
    except Exception as exc:
        raise normalize_inference_exception(exc, model="unet", file_id=req.file_id) from exc


@router.post(
    "/inference/yolo",
    response_model=YoloInferenceResponse,
    responses=YOLO_ERROR_RESPONSES,
)
def inference_yolo(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
) -> YoloInferenceResponse:
    try:
        return run_yolo_usecase(req, run_yolo_with_runtime)
    except Exception as exc:
        raise normalize_inference_exception(exc, model="yolo", file_id=req.file_id) from exc
