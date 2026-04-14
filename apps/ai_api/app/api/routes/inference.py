from fastapi import APIRouter, Depends

from app.api.deps import get_unet_runner, get_yolo_runner
from app.api.errors import to_http_exception
from app.presentation.requests.inference_request_dto import (
    InferenceUploadRequestDto,
    parse_inference_upload_request,
)
from app.usecases.run_unet_usecase import run_unet_usecase
from app.usecases.run_yolo_usecase import run_yolo_usecase
from packages.contracts.inference import UnetInferenceResponse, YoloInferenceResponse

router = APIRouter(tags=["inference"])


@router.post("/inference/unet", response_model=UnetInferenceResponse)
def inference_unet(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
    runner=Depends(get_unet_runner),
) -> UnetInferenceResponse:
    try:
        return run_unet_usecase(req, runner)
    except Exception as exc:
        raise to_http_exception(exc) from exc


@router.post("/inference/yolo", response_model=YoloInferenceResponse)
def inference_yolo(
    req: InferenceUploadRequestDto = Depends(parse_inference_upload_request),
    runner=Depends(get_yolo_runner),
) -> YoloInferenceResponse:
    try:
        return run_yolo_usecase(req, runner)
    except Exception as exc:
        raise to_http_exception(exc) from exc
