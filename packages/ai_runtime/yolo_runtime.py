from __future__ import annotations

import torch
from ultralytics import YOLO

_YOLO_MODEL = None


def _resolve_device(preferred: str, default_device: str) -> str:
    p = (preferred or "").strip().lower()
    if p:
        if p.startswith("cuda") and not torch.cuda.is_available():
            return "cpu"
        return p
    d = (default_device or "auto").strip().lower()
    if d == "cpu":
        return "cpu"
    if d.startswith("cuda"):
        return d if torch.cuda.is_available() else "cpu"
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def load_yolo_runtime(weights_path: str) -> YOLO:
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        _YOLO_MODEL = YOLO(weights_path)
    return _YOLO_MODEL


def infer_yolo_array(
    model: YOLO,
    image_bgr,
    *,
    conf: float = 0.25,
    device: str = "cpu",
):
    """Run YOLO inference for a single BGR image."""
    results = model.predict(
        source=image_bgr,
        imgsz=max(image_bgr.shape[:2]),
        conf=conf,
        device=device,
        verbose=False,
    )
    return results[0]


def run_yolo_inference_result(
    image_bgr,
    *,
    weights_path: str,
    conf_threshold: float,
    preferred_device: str = "",
    default_device: str = "auto",
):
    model = load_yolo_runtime(weights_path)
    device = _resolve_device(preferred_device, default_device)
    result = infer_yolo_array(model, image_bgr, conf=conf_threshold, device=device)
    return model, result, device

