from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SionnaRunResponseDto(BaseModel):
    sionna_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    imageUrl: str | None = None
    detail: str | None = None


def to_sionna_response(result: dict[str, Any]) -> SionnaRunResponseDto:
    artifacts = result.get("artifacts") or None
    image_url = None
    if artifacts is not None:
        image_url = artifacts.get("imageUrl")
        if image_url is None:
            image_url = artifacts.get("visualization_path")

    return SionnaRunResponseDto(
        sionna_run_id=str(result.get("sionna_run_id", "")),
        status=str(result.get("status", "failed")),
        metrics=result.get("metrics"),
        artifacts=artifacts,
        imageUrl=image_url,
        detail=result.get("error"),
    )
