from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import yaml

from packages.ai_runtime.unet_inference import infer_resize, infer_sliding_window
from packages.ai_runtime.unet_model import UNet

_UNET_MODEL = None
_UNET_CFG = None
_UNET_DEVICE = "cpu"


def _resolve_device(default_device: str) -> str:
    configured = (default_device or "auto").strip().lower()
    if configured == "cpu":
        return "cpu"
    if configured.startswith("cuda"):
        return configured if torch.cuda.is_available() else "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _fallback_probability_map(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    mask = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
    return (mask.astype(np.float32) / 255.0).clip(0.0, 1.0)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"UNet config must be a mapping: {path}")
    return data


def load_unet_runtime(
    *,
    config_path: str,
    checkpoint_path: str,
    default_device: str = "auto",
):
    global _UNET_MODEL, _UNET_CFG, _UNET_DEVICE
    if _UNET_MODEL is not None and _UNET_CFG is not None:
        return _UNET_MODEL, _UNET_CFG, _UNET_DEVICE

    cfg_path = Path(config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"UNet config not found: {cfg_path}")
    cfg = _load_yaml(cfg_path)
    _UNET_CFG = cfg

    ckpt = (checkpoint_path or "").strip()
    if not ckpt:
        return None, cfg, "cpu"

    ckpt_path = Path(ckpt)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"UNet checkpoint not found: {ckpt_path}")

    _UNET_DEVICE = _resolve_device(default_device)
    model = UNet(
        in_channels=int(cfg["model"]["in_channels"]),
        out_channels=int(cfg["model"]["out_channels"]),
    ).to(_UNET_DEVICE)
    state = torch.load(str(ckpt_path), map_location=_UNET_DEVICE)
    if isinstance(state, dict):
        if "model_state_dict" in state:
            state = state["model_state_dict"]
        elif "state_dict" in state:
            state = state["state_dict"]
    model.load_state_dict(state, strict=False)
    model.eval()
    _UNET_MODEL = model
    return _UNET_MODEL, _UNET_CFG, _UNET_DEVICE


def run_unet_probability_inference(
    image_bgr: np.ndarray,
    *,
    config_path: str,
    checkpoint_path: str,
    default_device: str = "auto",
) -> tuple[np.ndarray, dict]:
    model, cfg, device_name = load_unet_runtime(
        config_path=config_path,
        checkpoint_path=checkpoint_path,
        default_device=default_device,
    )
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    if model is None:
        prob_map = _fallback_probability_map(gray)
        return prob_map, {"model": "fallback-morphology", "device": "cpu", "mode": "fallback"}

    data_cfg = cfg["data"]
    infer_cfg = cfg.get("infer", {})
    image_size = int(data_cfg["image_size"])
    threshold = float(infer_cfg.get("threshold", 0.5))
    resize_mode = str(data_cfg.get("resize_mode", "letterbox"))
    patch_size = int(infer_cfg.get("patch_size") or data_cfg.get("train_patch_size") or image_size)
    stride = int(infer_cfg.get("stride") or max(1, patch_size // 2))
    use_sliding = bool(infer_cfg.get("sliding_window", True))

    device = torch.device(device_name)
    if use_sliding:
        _mask, prob_map = infer_sliding_window(
            rgb,
            model,
            device,
            patch_size=patch_size,
            image_size=image_size,
            stride=stride,
            resize_mode=resize_mode,  # type: ignore[arg-type]
            threshold=threshold,
        )
        mode = "sliding"
    else:
        _mask, prob_map = infer_resize(
            rgb,
            model,
            device,
            image_size=image_size,
            threshold=threshold,
        )
        mode = "resize"
    prob_map = prob_map.astype(np.float32, copy=False)
    return prob_map, {"model": "unet-checkpoint", "device": device_name, "mode": mode}

