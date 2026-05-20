from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────
# Analysis priors — AI 서버가 U-Net/YOLO 와 함께 사전 분석 결과를 같이 내려줌.
# 백엔드는 이 priors 를 받으면 그대로 사용하고, 없으면 내부 OCR/line 으로 fallback.
#
# 좌표계 (coordinate_space):
#   - "source_image": 원본 업로드 이미지 좌표 (ROI crop 전)
#   - "roi_image":    ROI crop 후 좌표
#   - "letterbox_image": U-Net 입력용 letterbox 후 좌표
#
# 모든 prior 는 어느 좌표계에 정의됐는지 명시. ROI 가 도입돼도 변환 가능.
# ─────────────────────────────────────────────────────────────────────────
class OcrPrior(BaseModel):
    """OCR 항목 (text + 위치 + 의미 분류).

    `kind` 는 사용처를 결정:
      - "dimension":  치수 (예: "3,500", "3500", "3.5m") → scale 추정 입력
      - "room_label": 방 이름 (예: "안방", "거실") → room metadata
      - "scale":      축척 표기 (예: "SCALE 1/80") → scale 직접 추정
      - "title":      도면 제목/주석 — 벽으로 오탐 안 되게 penalty
      - "unknown":    분류 안됨

    `parsed_value_m` 는 dimension 일 때만 채워짐 (mm/cm/m parsing 결과).
    `orientation` 은 bbox aspect 로 결정 (가로 라벨 → horizontal).
    """
    text: str
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float | None = None
    kind: Literal["dimension", "room_label", "scale", "title", "unknown"] | None = None
    parsed_value_m: float | None = None
    orientation: Literal["horizontal", "vertical", "unknown"] | None = None
    coordinate_space: Literal["source_image", "roi_image", "letterbox_image"] = "source_image"


class LinePrior(BaseModel):
    """OpenCV/Hough/LSD 선분 후보 — 벽 추출 정답이 아닌 신호 보조용.

    `kind` 는 사용처를 결정:
      - "wall_candidate":   긴 H/V 선분 → wall scoring 의 line_alignment 입력
      - "dimension_line":   치수 가이드 라인 (양 끝에 tick) → tick-interval scale 추정
      - "tick":             dimension line 의 short perpendicular 표시
      - "unknown":          분류 안됨 (낮은 신뢰도)

    `source` 는 어느 알고리즘이 추출했는지 — 디버깅용.
    """
    x1: float
    y1: float
    x2: float
    y2: float
    length_px: float | None = None
    angle_deg: float | None = None       # 0=수평, 90=수직
    orientation: Literal["horizontal", "vertical", "diagonal"] | None = None
    kind: Literal["wall_candidate", "dimension_line", "tick", "unknown"] | None = None
    confidence: float | None = None
    source: Literal["hough", "lsd", "cv2"] | None = None
    coordinate_space: Literal["source_image", "roi_image", "letterbox_image"] = "source_image"


class RoiTransform(BaseModel):
    """원본 이미지 → ROI 사이 변환. ROI 없어도 전체 이미지로 표현 가능.

    호출자가 ROI 좌표를 원본으로 복원하려면:
      x_source = roi_x + (x_roi / output_width)  * roi_width   (output 이 있을 때)
      y_source = roi_y + (y_roi / output_height) * roi_height

    또는 단순히 `scale_x`, `scale_y` 곱하고 offset 더하기.
    """
    source_width: int
    source_height: int

    # ROI bbox (원본 이미지 좌표)
    roi_x: float = 0.0
    roi_y: float = 0.0
    roi_width: float
    roi_height: float

    # ROI 가 resize 됐을 경우 출력 크기 (없으면 ROI 그대로)
    output_width: int | None = None
    output_height: int | None = None

    # 편의: roi_image → source_image 변환 비율 (output 기준)
    scale_x: float = 1.0
    scale_y: float = 1.0

    # 이 RoiTransform 이 어느 좌표계를 "기준"으로 삼는지
    coordinate_space: Literal["source_image", "roi_image"] = "roi_image"


class UnetOutput(BaseModel):
    wallProbNpyPath: str
    wallProbOverlayPath: str
    # ── 사전 분석 priors (optional) ─────────────────────────────────
    # 채워져 있으면 백엔드 wall_extraction 이 자체 OCR/line 건너뛰고 그대로 사용.
    # 없으면 백엔드가 fallback 으로 자체 추출 (현재 호환 동작).
    ocrPriors: Optional[list[OcrPrior]] = None
    linePriors: Optional[list[LinePrior]] = None
    roiTransform: Optional[RoiTransform] = None


class UnetMetrics(BaseModel):
    wallConnectivity: float
    model: str
    device: str
    filename: str
    note: str
    shape: list[int]
    dtype: str
    minProb: float
    maxProb: float
    overlayPath: str


class UnetInferenceResponse(BaseModel):
    status: Literal["ok"]
    task: Literal["unet"]
    fileId: str
    output: UnetOutput
    metrics: UnetMetrics


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: list[int]


class YoloOutput(BaseModel):
    detections: list[Detection]
    previewPath: str


class YoloMetrics(BaseModel):
    detectionCount: int
    avgConfidence: float
    model: str
    threshold: float
    device: str
    filename: str
    previewPath: str


class YoloInferenceResponse(BaseModel):
    status: Literal["ok"]
    task: Literal["yolo"]
    fileId: str
    output: YoloOutput
    metrics: YoloMetrics

