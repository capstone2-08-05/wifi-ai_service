from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from packages.contracts.inference import YoloInferenceResponse


def run_yolo_usecase(req: InferenceUploadRequestDto, runner) -> YoloInferenceResponse:
    detections, preview_path, metrics = runner(req.file_id, req.image_bytes, req.filename)
    return YoloInferenceResponse(
        status="ok",
        task="yolo",
        fileId=req.file_id,
        output={"detections": detections, "previewPath": preview_path},
        metrics=metrics,
    )


__all__ = ["run_yolo_usecase"]
