"""Shared FastAPI dependencies."""

from app.infrastructure.ai_runtime.inference_runner import (
    run_unet_with_runtime,
    run_yolo_with_runtime,
)
from app.infrastructure.sionna.sionna_preview_runner import run_sionna_preview_with_runtime


def get_unet_runner():
    return run_unet_with_runtime


def get_yolo_runner():
    return run_yolo_with_runtime


def get_sionna_preview_runner():
    return run_sionna_preview_with_runtime
