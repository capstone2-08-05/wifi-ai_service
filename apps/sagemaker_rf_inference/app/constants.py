"""상수 및 enum 중앙 관리 (RF inference container).

도메인 문자열은 모두 `class X(str, Enum)` 패턴, 수치/경로 기본값은 모듈 상수.
다른 모듈은 여기서 import 만 한다.

(참고: StrEnum 은 Python 3.11+ 전용. 호환을 위해 `class X(str, Enum)` 패턴 사용.)
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path


# ============================================================
# Versioning
# ============================================================
SCHEMA_VERSION = "1.0"
CONTAINER_VERSION = os.getenv("CONTAINER_VERSION", "rf-inference@0.1.0")


# ============================================================
# 디렉토리
# ============================================================
APP_DIR = Path(__file__).resolve().parent
APP_ROOT = APP_DIR.parent
SCHEMA_DIR = APP_ROOT / "schemas"


# ============================================================
# 시뮬레이션 기본값 (input.options 미지정 시 사용)
# ============================================================
DEFAULT_RESOLUTION_M = 0.5
DEFAULT_MEASUREMENT_PLANE_Z_M = 1.0
DEFAULT_MAX_DEPTH = 3
DEFAULT_SAMPLES_PER_TX = 100_000
DEFAULT_SEED = 42

# heatmap 시각화에 사용할 dBm 범위 (clipping).
HEATMAP_DBM_MIN = -100.0
HEATMAP_DBM_MAX = -30.0
INVALID_DBM_THRESHOLD = -200.0  # sionna_runtime 과 동일


# ============================================================
# 환경변수 이름
# ============================================================
class EnvVar(str, Enum):
    DEFAULT_DEVICE = "DEFAULT_DEVICE"
    CONTAINER_VERSION = "CONTAINER_VERSION"
    AWS_S3_ENDPOINT_URL = "AWS_S3_ENDPOINT_URL"
    AWS_REGION = "AWS_REGION"
    AWS_DEFAULT_REGION = "AWS_DEFAULT_REGION"


# ============================================================
# output_prefix 하위 고정 파일명
# ============================================================
class OutputFile(str, Enum):
    """계약 README 의 '출력 파일 규약' 표와 일치해야 함."""
    RESULT = "result.json"
    FAILURE = "failure.json"
    HEATMAP = "heatmap.png"
    RADIO_MAP = "radio_map.npy"

    @property
    def uri_key(self) -> str:
        """result.json 의 outputs 에서 쓰는 키. 예: heatmap.png → heatmap_s3_uri."""
        stem = self.value.rsplit(".", 1)[0]
        return f"{stem}_s3_uri"


# ============================================================
# stages 키 (result.json 의 시간 측정)
# ============================================================
class StageMs(str, Enum):
    DOWNLOAD_SCENE = "download_scene_ms"
    PARSE_SCENE = "parse_scene_ms"
    RAY_TRACING = "ray_tracing_ms"
    UPLOAD = "upload_ms"
    TOTAL = "total_ms"


# ============================================================
# failure.json 의 error.code
# ============================================================
class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    SCENE_DOWNLOAD_FAILED = "SCENE_DOWNLOAD_FAILED"
    SCENE_PARSE_FAILED = "SCENE_PARSE_FAILED"
    SIMULATION_FAILED = "SIMULATION_FAILED"
    OUTPUT_UPLOAD_FAILED = "OUTPUT_UPLOAD_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================
# failure.json 의 error.stage
# ============================================================
class ErrorStage(str, Enum):
    VALIDATE_INPUT = "validate_input"
    DOWNLOAD_SCENE = "download_scene"
    PARSE_SCENE = "parse_scene"
    RAY_TRACING = "ray_tracing"
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
