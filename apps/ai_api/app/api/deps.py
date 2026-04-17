"""Shared FastAPI dependencies."""

from app.infrastructure.ai_runtime.inference_runner import (
    run_unet_with_runtime,
    run_yolo_with_runtime,
)
from app.infrastructure.ai_runtime.sionna_gateway import run_sionna_with_runtime


def get_unet_runner():
    return run_unet_with_runtime


def get_yolo_runner():
    return run_yolo_with_runtime


def get_sionna_runner():
    return run_sionna_with_runtime
