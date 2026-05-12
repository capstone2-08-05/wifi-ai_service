"""raw 추론 결과 → 컨테이너 출력 파일 5종 생성."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.constants import (
    DEFAULT_UNET_THRESHOLD,
    OVERLAY_HEATMAP_ALPHA,
    OVERLAY_SOURCE_ALPHA,
    SCHEMA_VERSION,
)


def encode_wall_mask_png(prob_map: np.ndarray, threshold: float = DEFAULT_UNET_THRESHOLD) -> bytes:
    """확률 맵 → 0/255 binary PNG bytes."""
    mask = (prob_map >= threshold).astype(np.uint8) * 255
    ok, buf = cv2.imencode(".png", mask)
    if not ok:
        raise RuntimeError("cv2.imencode failed for wall_mask.png")
    return buf.tobytes()


def encode_preview_overlay_png(
    source_bgr: np.ndarray,
    prob_map: np.ndarray,
    detections: list[dict[str, Any]],
) -> bytes:
    """원본 + 벽 확률 heatmap + YOLO bbox 시각화 PNG bytes."""
    if prob_map.shape[:2] != source_bgr.shape[:2]:
        # 보호적으로 리사이즈
        prob_resized = cv2.resize(
            prob_map.astype(np.float32),
            (source_bgr.shape[1], source_bgr.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
    else:
        prob_resized = prob_map.astype(np.float32, copy=False)

    heatmap = cv2.applyColorMap((np.clip(prob_resized, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(source_bgr, OVERLAY_SOURCE_ALPHA, heatmap, OVERLAY_HEATMAP_ALPHA, 0.0)

    for det in detections:
        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = (int(v) for v in bbox)
        cls = det.get("class_name") or str(det.get("class_id", "?"))
        conf = det.get("confidence")
        label = f"{cls} {conf:.2f}" if isinstance(conf, (int, float)) else str(cls)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            overlay,
            label,
            (x1, max(15, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

    ok, buf = cv2.imencode(".png", overlay)
    if not ok:
        raise RuntimeError("cv2.imencode failed for preview_overlay.png")
    return buf.tobytes()


def build_detections_payload(
    detections: list[dict[str, Any]],
    *,
    image_size: tuple[int, int],
    model_name: str,
    threshold: float,
    device: str,
) -> dict[str, Any]:
    """YOLO raw detection 결과를 JSON 페이로드로 구조화."""
    width_px, height_px = image_size
    return {
        "schema_version": SCHEMA_VERSION,
        "model": model_name,
        "threshold": float(threshold),
        "device": device,
        "image": {"width_px": int(width_px), "height_px": int(height_px)},
        "detections": list(detections),
    }
