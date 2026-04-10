from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from app.core.ai_floorplan_bridge import AI_FLOORPLAN_ROOT  # noqa: F401 (import side effect for path)
from app.core.settings import OUTPUT_DIR, default_device, unet_checkpoint_path, unet_config_path
from src.runtime.unet_runtime import load_unet_runtime, run_unet_probability_inference  # type: ignore[reportMissingImports]

UNET_OUTPUT_DIR = OUTPUT_DIR / "unet"


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode uploaded image bytes")
    return img


def preload_unet_model() -> None:
    load_unet_runtime(
        config_path=unet_config_path(),
        checkpoint_path=unet_checkpoint_path(),
        default_device=default_device(),
    )


def run_unet_inference(file_id: str, image_bytes: bytes, filename: str) -> tuple[str, dict]:
    UNET_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bgr = _decode_bgr(image_bytes)

    run_id = file_id or uuid4().hex
    run_dir = UNET_OUTPUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prob_map, rt = run_unet_probability_inference(
        bgr,
        config_path=unet_config_path(),
        checkpoint_path=unet_checkpoint_path(),
        default_device=default_device(),
    )
    prob_map = prob_map.astype(np.float32, copy=False)
    model_name = str(rt["model"])
    note = (
        "Set UNET_CHECKPOINT_PATH for real U-Net inference"
        if model_name == "fallback-morphology"
        else f"checkpoint inference ({rt['mode']})"
    )

    stem = Path(filename).stem or "input"
    out_npy = run_dir / f"{stem}_wall_prob.npy"
    np.save(out_npy, prob_map)
    out_overlay = run_dir / f"{stem}_wall_prob_overlay.png"

    heatmap = cv2.applyColorMap((prob_map * 255).astype(np.uint8), cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(bgr, 0.55, heatmap, 0.45, 0.0)
    cv2.imwrite(str(out_overlay), overlay)

    wall_pixels = int((prob_map >= 0.5).sum())
    total_pixels = int(prob_map.size)
    connectivity = round(wall_pixels / max(total_pixels, 1), 4)
    metrics = {
        "wallConnectivity": connectivity,
        "model": model_name,
        "device": str(rt["device"]),
        "filename": filename,
        "note": note,
        "shape": [int(prob_map.shape[0]), int(prob_map.shape[1])],
        "dtype": str(prob_map.dtype),
        "minProb": float(prob_map.min()),
        "maxProb": float(prob_map.max()),
        "overlayPath": str(out_overlay),
    }
    return str(out_npy), metrics
