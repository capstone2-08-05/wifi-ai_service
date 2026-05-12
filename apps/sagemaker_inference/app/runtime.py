"""모델 preload + 디바이스 결정.

기존 packages/ai_runtime 의 함수를 그대로 사용. SageMaker 컨테이너는
startup 시 1회 preload 후 메모리에 캐시한다.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import torch
import yaml

from app.constants import (
    DEFAULT_DEVICE_MODE,
    DEFAULT_UNET_CHECKPOINT_PATH,
    DEFAULT_UNET_CONFIG_PATH,
    DEFAULT_YOLO_CONFIG_PATH,
    DEFAULT_YOLO_WEIGHTS_PATH,
    EnvVar,
)
from packages.ai_runtime.unet_runtime import load_unet_runtime
from packages.ai_runtime.yolo_runtime import load_yolo_runtime

logger = logging.getLogger(__name__)


def unet_checkpoint_path() -> str:
    return os.getenv(EnvVar.UNET_CHECKPOINT_PATH, DEFAULT_UNET_CHECKPOINT_PATH).strip()


def unet_config_path() -> str:
    return os.getenv(EnvVar.UNET_CONFIG_PATH, DEFAULT_UNET_CONFIG_PATH).strip()


def yolo_weights_path() -> str:
    return os.getenv(EnvVar.YOLO_MODEL_PATH, DEFAULT_YOLO_WEIGHTS_PATH).strip()


def yolo_config_path() -> str:
    return os.getenv(EnvVar.YOLO_CONFIG_PATH, DEFAULT_YOLO_CONFIG_PATH).strip()


def default_device() -> str:
    return os.getenv(EnvVar.DEFAULT_DEVICE, DEFAULT_DEVICE_MODE).strip().lower()


def resolve_device(default_device_str: str) -> str:
    configured = (default_device_str or DEFAULT_DEVICE_MODE).strip().lower()
    if configured == "cpu":
        return "cpu"
    if configured.startswith("cuda"):
        return configured if torch.cuda.is_available() else "cpu"
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def load_yaml(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config must be a mapping: {path}")
    return data


_UNET_CFG: dict[str, Any] | None = None
_YOLO_CFG: dict[str, Any] | None = None


def get_unet_config() -> dict[str, Any]:
    global _UNET_CFG
    if _UNET_CFG is None:
        _UNET_CFG = load_yaml(unet_config_path())
    return _UNET_CFG


def get_yolo_config() -> dict[str, Any]:
    global _YOLO_CFG
    if _YOLO_CFG is None:
        _YOLO_CFG = load_yaml(yolo_config_path())
    return _YOLO_CFG


def preload_all() -> dict[str, Any]:
    """Startup 시 호출. CUDA 사용 여부 및 모델 로딩 결과 로깅."""
    cuda_avail = torch.cuda.is_available()
    device = resolve_device(default_device())
    logger.info(
        "preload_all: torch=%s cuda_available=%s device=%s device_count=%d",
        torch.__version__,
        cuda_avail,
        device,
        torch.cuda.device_count() if cuda_avail else 0,
    )

    info: dict[str, Any] = {
        "torch_version": torch.__version__,
        "cuda_available": cuda_avail,
        "device": device,
    }

    # U-Net
    try:
        get_unet_config()
        load_unet_runtime(
            config_path=unet_config_path(),
            checkpoint_path=unet_checkpoint_path(),
            default_device=default_device(),
        )
        info["unet"] = {"loaded": True, "checkpoint": unet_checkpoint_path()}
        logger.info("preload_all: U-Net loaded from %s", unet_checkpoint_path())
    except Exception as exc:
        info["unet"] = {"loaded": False, "error": str(exc)}
        logger.exception("preload_all: U-Net preload failed")

    # YOLO
    try:
        load_yolo_runtime(yolo_weights_path())
        info["yolo"] = {"loaded": True, "weights": yolo_weights_path()}
        logger.info("preload_all: YOLO loaded from %s", yolo_weights_path())
    except Exception as exc:
        info["yolo"] = {"loaded": False, "error": str(exc)}
        logger.exception("preload_all: YOLO preload failed")

    return info
