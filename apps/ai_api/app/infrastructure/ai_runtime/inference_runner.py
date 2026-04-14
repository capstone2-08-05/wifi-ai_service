from app.infrastructure.ai_runtime.unet_gateway import run_unet_inference
from app.infrastructure.ai_runtime.yolo_gateway import run_yolo_inference


def run_unet_with_runtime(file_id: str, image_bytes: bytes, filename: str) -> tuple[str, dict]:
    return run_unet_inference(file_id, image_bytes, filename)


def run_yolo_with_runtime(file_id: str, image_bytes: bytes, filename: str) -> tuple[list[dict], str, dict]:
    return run_yolo_inference(file_id, image_bytes, filename)
