"""상수 및 enum 중앙 관리.

도메인 문자열은 모두 StrEnum 으로, 수치/경로 기본값은 모듈 상수로 정의.
다른 모듈은 여기서 import 만 한다.
"""
from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path


# ============================================================
# Versioning
# ============================================================
SCHEMA_VERSION = "1.0"
CONTAINER_VERSION = os.getenv("CONTAINER_VERSION", "ai-inference@0.1.0")


# ============================================================
# 디렉토리
# ============================================================
APP_DIR = Path(__file__).resolve().parent
APP_ROOT = APP_DIR.parent
SCHEMA_DIR = APP_ROOT / "schemas"


# ============================================================
# 추론 파라미터 기본값
# ============================================================
DEFAULT_UNET_THRESHOLD = 0.5
DEFAULT_YOLO_CONF_THRESHOLD = 0.25

# Preview overlay 시각화 alpha
OVERLAY_SOURCE_ALPHA = 0.55
OVERLAY_HEATMAP_ALPHA = 0.45


# ============================================================
# 컨테이너 모델/설정 기본 경로 (Dockerfile ENV 와 일치)
# ============================================================
DEFAULT_UNET_CHECKPOINT_PATH = "/opt/ml/model/unet/best_unet.pth"
DEFAULT_UNET_CONFIG_PATH = "/opt/ml/configs/unet_inference.yaml"
DEFAULT_YOLO_WEIGHTS_PATH = "/opt/ml/model/yolo/best.pt"
DEFAULT_YOLO_CONFIG_PATH = "/opt/ml/configs/yolo_inference.yaml"
DEFAULT_DEVICE_MODE = "auto"


# ============================================================
# 환경변수 이름
# ============================================================
class EnvVar(StrEnum):
    UNET_CHECKPOINT_PATH = "UNET_CHECKPOINT_PATH"
    UNET_CONFIG_PATH = "UNET_CONFIG_PATH"
    YOLO_MODEL_PATH = "YOLO_MODEL_PATH"
    YOLO_CONFIG_PATH = "YOLO_CONFIG_PATH"
    DEFAULT_DEVICE = "DEFAULT_DEVICE"
    CONTAINER_VERSION = "CONTAINER_VERSION"
    AWS_S3_ENDPOINT_URL = "AWS_S3_ENDPOINT_URL"
    AWS_REGION = "AWS_REGION"
    AWS_DEFAULT_REGION = "AWS_DEFAULT_REGION"


# ============================================================
# output_prefix 하위 고정 파일명
# ============================================================
class OutputFile(StrEnum):
    """계약 README 의 "출력 파일 규약" 표와 일치해야 함."""
    RESULT = "result.json"
    FAILURE = "failure.json"
    WALL_MASK = "wall_mask.png"
    WALL_PROB_MAP = "wall_prob_map.npy"
    DETECTIONS = "detections.json"
    PREVIEW_OVERLAY = "preview_overlay.png"

    @property
    def uri_key(self) -> str:
        """result.json 의 outputs 안에서 쓰는 키. 예: wall_mask.png → wall_mask_s3_uri."""
        stem = self.value.rsplit(".", 1)[0]
        return f"{stem}_s3_uri"


# ============================================================
# stages 키 (result.json 의 시간 측정)
# ============================================================
class StageMs(StrEnum):
    DOWNLOAD = "download_ms"
    UNET = "unet_ms"
    YOLO = "yolo_ms"
    UPLOAD = "upload_ms"
    TOTAL = "total_ms"


# ============================================================
# failure.json 의 error.code
# ============================================================
class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    SOURCE_IMAGE_DOWNLOAD_FAILED = "SOURCE_IMAGE_DOWNLOAD_FAILED"
    SOURCE_IMAGE_DECODE_FAILED = "SOURCE_IMAGE_DECODE_FAILED"
    UNET_INFERENCE_FAILED = "UNET_INFERENCE_FAILED"
    YOLO_INFERENCE_FAILED = "YOLO_INFERENCE_FAILED"
    OUTPUT_UPLOAD_FAILED = "OUTPUT_UPLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================
# failure.json 의 error.stage
# ============================================================
class ErrorStage(StrEnum):
    VALIDATE_INPUT = "validate_input"
    DOWNLOAD_SOURCE = "download_source"
    DECODE_IMAGE = "decode_image"
    WALL_SEGMENTATION = "wall_segmentation"
    OBJECT_DETECTION = "object_detection"
    UPLOAD_OUTPUTS = "upload_outputs"
    UNKNOWN = "unknown"


# ============================================================
# HTTP status code (main.py)
# ============================================================
class HttpStatus:
    """주요 status code 의 의미적 별칭."""
    OK = 200
    READY = 200
    CONTRACT_ERROR = 400
    NOT_READY = 503
    HANDLER_ERROR = 502
    INTERNAL_ERROR = 500
