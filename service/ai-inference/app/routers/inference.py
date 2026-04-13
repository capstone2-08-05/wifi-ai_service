from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.inference import UnetInferenceResponse, YoloInferenceResponse
from app.services.unet_inference_service import run_unet_inference
from app.services.yolo_inference_service import run_yolo_inference

router = APIRouter(tags=["inference"])
_ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}


def _validate_image_upload(file: UploadFile) -> None:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    ext = filename.lower().rsplit(".", 1)
    ext = f".{ext[-1]}" if len(ext) > 1 else ""
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: png, jpg, jpeg",
        )


async def _run_unet_inference(file_id: str, file: UploadFile) -> UnetInferenceResponse:
    try:
        _validate_image_upload(file)
        image_bytes = await file.read()
        prob_map_path, metrics = run_unet_inference(file_id, image_bytes, file.filename or "input")
        return UnetInferenceResponse(
            status="ok",
            task="unet",
            fileId=file_id,
            output={
                "wallProbNpyPath": prob_map_path,
                "wallProbOverlayPath": metrics["overlayPath"],
            },
            metrics=metrics,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _run_yolo_inference(file_id: str, file: UploadFile) -> YoloInferenceResponse:
    try:
        _validate_image_upload(file)
        image_bytes = await file.read()
        detections, preview_path, metrics = run_yolo_inference(file_id, image_bytes, file.filename or "input")
        return YoloInferenceResponse(
            status="ok",
            task="yolo",
            fileId=file_id,
            output={"detections": detections, "previewPath": preview_path},
            metrics=metrics,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/inference/unet", response_model=UnetInferenceResponse)
async def inference_unet(
    file_id: str = Form(...), file: UploadFile = File(...)
) -> UnetInferenceResponse:
    return await _run_unet_inference(file_id=file_id, file=file)


@router.post("/inference/yolo", response_model=YoloInferenceResponse)
async def inference_yolo(
    file_id: str = Form(...), file: UploadFile = File(...)
) -> YoloInferenceResponse:
    return await _run_yolo_inference(file_id=file_id, file=file)
