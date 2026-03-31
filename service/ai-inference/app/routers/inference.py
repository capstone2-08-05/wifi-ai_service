from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.wall_unet import predict_wall_mask
from app.services.yolo_detect import detect_objects

router = APIRouter(tags=["inference"])


@router.post("/wall/unet")
async def wall_unet(file_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    try:
        image_bytes = await file.read()
        mask_path, metrics = predict_wall_mask(file_id, image_bytes, file.filename or "input")
        return {"status": "ok", "maskPath": mask_path, "metrics": metrics}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/objects/yolo")
async def objects_yolo(file_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    try:
        image_bytes = await file.read()
        detections, metrics = detect_objects(file_id, image_bytes, file.filename or "input")
        return {"status": "ok", "detections": detections, "metrics": metrics}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
