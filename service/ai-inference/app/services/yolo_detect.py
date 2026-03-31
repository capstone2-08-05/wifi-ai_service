from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from app.core.settings import OUTPUT_DIR, yolo_conf_threshold, yolo_device, yolo_model_path

YOLO_OUTPUT_DIR = OUTPUT_DIR / "yolo"
_YOLO_MODEL = None


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode uploaded image bytes")
    return img


def _load_model() -> YOLO:
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        _YOLO_MODEL = YOLO(yolo_model_path())
    return _YOLO_MODEL


def detect_objects(file_id: str, image_bytes: bytes, filename: str) -> tuple[list[dict], dict]:
    YOLO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img = _decode_bgr(image_bytes)

    model = _load_model()
    conf = yolo_conf_threshold()
    device = yolo_device() or None

    results = model.predict(source=img, conf=conf, device=device, verbose=False)
    result = results[0]

    detections = []
    if result.boxes is not None:
        names = model.names if isinstance(model.names, dict) else {}
        for box in result.boxes:
            cls_id = int(box.cls.item())
            conf_score = float(box.conf.item())
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class": names.get(cls_id, str(cls_id)),
                    "confidence": round(conf_score, 4),
                    "bbox": [x1, y1, x2, y2],
                }
            )

    plotted = result.plot()
    preview_path = YOLO_OUTPUT_DIR / f"{file_id}_preview.png"
    cv2.imwrite(str(preview_path), plotted)

    avg_conf = round(sum(d["confidence"] for d in detections) / max(len(detections), 1), 4)
    metrics = {
        "detectionCount": len(detections),
        "avgConfidence": avg_conf,
        "model": yolo_model_path(),
        "threshold": conf,
        "filename": filename,
        "previewPath": str(preview_path),
    }
    return detections, metrics
