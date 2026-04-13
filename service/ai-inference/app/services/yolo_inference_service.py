from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import yaml

from app.core.ai_floorplan_bridge import AI_FLOORPLAN_ROOT  # noqa: F401 (import side effect for path)
from app.core.settings import (
    OUTPUT_DIR,
    default_device,
    yolo_conf_threshold,
    yolo_config_path,
    yolo_device,
    yolo_model_path,
)
from src.runtime.yolo_runtime import load_yolo_runtime, run_yolo_inference_result

YOLO_OUTPUT_DIR = OUTPUT_DIR / "yolo"
_YOLO_CFG = None


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode uploaded image bytes")
    return img


def preload_yolo_model() -> None:
    cfg = _load_yolo_config()
    weights = str(cfg.get("model", {}).get("weights_path", "")).strip() or yolo_model_path()
    load_yolo_runtime(weights)


def _load_yolo_config() -> dict:
    global _YOLO_CFG
    if _YOLO_CFG is not None:
        return _YOLO_CFG

    cfg_path = Path(yolo_config_path())
    if not cfg_path.exists():
        raise FileNotFoundError(f"YOLO config not found: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        _YOLO_CFG = yaml.safe_load(f) or {}
    return _YOLO_CFG


def run_yolo_inference(file_id: str, image_bytes: bytes, filename: str) -> tuple[list[dict], str, dict]:
    YOLO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img = _decode_bgr(image_bytes)

    run_id = file_id or uuid4().hex
    run_dir = YOLO_OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg = _load_yolo_config()
    infer_cfg = cfg.get("infer", {})
    model_cfg = cfg.get("model", {})
    conf = float(infer_cfg.get("conf_threshold", yolo_conf_threshold()))
    preferred_device = str(infer_cfg.get("device", "")).strip() or yolo_device()
    weights_path = str(model_cfg.get("weights_path", "")).strip() or yolo_model_path()
    model, result, device = run_yolo_inference_result(
        img,
        weights_path=weights_path,
        conf_threshold=conf,
        preferred_device=preferred_device,
        default_device=default_device(),
    )

    detections = []
    if result.boxes is not None:
        names = model.names if isinstance(model.names, dict) else {}
        for box in result.boxes:
            cls_id = int(box.cls.item())
            conf_score = float(box.conf.item())
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class_id": cls_id,
                    "class_name": names.get(cls_id, str(cls_id)),
                    "confidence": round(conf_score, 4),
                    "bbox": [x1, y1, x2, y2],
                }
            )

    plotted = result.plot()
    stem = Path(filename).stem or "input"
    preview_path = run_dir / f"{stem}_preview.png"
    cv2.imwrite(str(preview_path), plotted)

    avg_conf = round(sum(d["confidence"] for d in detections) / max(len(detections), 1), 4)
    metrics = {
        "detectionCount": len(detections),
        "avgConfidence": avg_conf,
        "model": weights_path,
        "threshold": conf,
        "device": device,
        "filename": filename,
        "previewPath": str(preview_path),
    }
    return detections, str(preview_path), metrics
