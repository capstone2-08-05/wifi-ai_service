"""radio map (dBm) → heatmap PNG 인코딩.

matplotlib 등 무거운 의존성 없이 numpy + opencv 로 컬러맵 적용.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.constants import HEATMAP_DBM_MAX, HEATMAP_DBM_MIN, INVALID_DBM_THRESHOLD


def encode_heatmap_png(
    dbm_map: np.ndarray,
    *,
    dbm_min: float = HEATMAP_DBM_MIN,
    dbm_max: float = HEATMAP_DBM_MAX,
) -> bytes:
    """2D dBm array → 컬러맵 적용된 PNG bytes.

    매핑:
      - dbm >= dbm_max → 빨강 (강한 신호)
      - dbm <= dbm_min → 파랑 (약한 신호)
      - INVALID_DBM_THRESHOLD 이하 셀 → 투명 (RGBA 알파=0)
    """
    arr = np.asarray(dbm_map, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"dbm_map must be 2D, got shape {arr.shape}")

    valid = arr > INVALID_DBM_THRESHOLD

    # 정규화 [0, 1] (dbm_min → 0, dbm_max → 1)
    span = max(1e-6, float(dbm_max - dbm_min))
    norm = np.clip((arr - dbm_min) / span, 0.0, 1.0)
    norm_uint8 = (norm * 255.0).astype(np.uint8)

    # JET 컬러맵 (파랑→청록→노랑→빨강): 약한 신호 파랑, 강한 신호 빨강
    bgr = cv2.applyColorMap(norm_uint8, cv2.COLORMAP_JET)

    # invalid 셀은 알파 0 (투명) 으로
    rgba = np.dstack(
        [bgr[:, :, 2], bgr[:, :, 1], bgr[:, :, 0], np.where(valid, 255, 0).astype(np.uint8)]
    )

    success, buf = cv2.imencode(".png", rgba)
    if not success:
        raise RuntimeError("cv2.imencode failed for heatmap PNG")
    return bytes(buf.tobytes())
