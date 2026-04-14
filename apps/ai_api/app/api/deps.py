"""Shared FastAPI dependencies."""

from app.infrastructure.ai_runtime.inference_runner import (
    run_unet_with_runtime,
    run_yolo_with_runtime,
)
from app.infrastructure.rf.rf_preview_runner import run_rf_preview_with_rf_core


def get_unet_runner():
    return run_unet_with_runtime


def get_yolo_runner():
    return run_yolo_with_runtime


def get_rf_preview_runner():
    return run_rf_preview_with_rf_core
