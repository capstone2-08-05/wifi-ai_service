"""Shared FastAPI dependencies."""

from app.infrastructure.ai_runtime.inference_runner import (
    run_unet_with_runtime,
    run_yolo_with_runtime,
)
from app.infrastructure.rf.rf_preview_runner import run_rf_preview_with_rf_core
from app.infrastructure.rf.sionna_rt_poc_runner import build_sionna_rt_poc_plan


def get_unet_runner():
    return run_unet_with_runtime


def get_yolo_runner():
    return run_yolo_with_runtime


def get_rf_preview_runner():
    return run_rf_preview_with_rf_core


def get_sionna_rt_poc_runner():
    return build_sionna_rt_poc_plan
