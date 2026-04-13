"""Shared DTO schemas (floorplan handoff, inference responses, etc.)."""

from app.schemas.inference import UnetInferenceResponse, YoloInferenceResponse

__all__ = ["UnetInferenceResponse", "YoloInferenceResponse"]
