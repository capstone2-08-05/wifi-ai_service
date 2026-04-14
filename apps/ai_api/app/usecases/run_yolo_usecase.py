from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto
from app.presentation.responses.inference_response_dto import build_yolo_response


def run_yolo_usecase(req: InferenceUploadRequestDto, runner):
    detections, preview_path, metrics = runner(req.file_id, req.image_bytes, req.filename)
    return build_yolo_response(req.file_id, detections, preview_path, metrics)


__all__ = ["run_yolo_usecase"]
