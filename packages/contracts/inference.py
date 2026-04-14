from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class UnetOutput(BaseModel):
    wallProbNpyPath: str
    wallProbOverlayPath: str


class UnetMetrics(BaseModel):
    wallConnectivity: float
    model: str
    device: str
    filename: str
    note: str
    shape: list[int]
    dtype: str
    minProb: float
    maxProb: float
    overlayPath: str


class UnetInferenceResponse(BaseModel):
    status: Literal["ok"]
    task: Literal["unet"]
    fileId: str
    output: UnetOutput
    metrics: UnetMetrics


class Detection(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: list[int]


class YoloOutput(BaseModel):
    detections: list[Detection]
    previewPath: str


class YoloMetrics(BaseModel):
    detectionCount: int
    avgConfidence: float
    model: str
    threshold: float
    device: str
    filename: str
    previewPath: str


class YoloInferenceResponse(BaseModel):
    status: Literal["ok"]
    task: Literal["yolo"]
    fileId: str
    output: YoloOutput
    metrics: YoloMetrics

