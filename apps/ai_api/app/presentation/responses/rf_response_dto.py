from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.entities.rf_preview_entity import RfRunPathsEntity
from packages.rf_core.services.rf_run_service import RfRunResult


class RfRunResponseDto(BaseModel):
    rf_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    output_root: str | None = None
    paths: RfRunPathsEntity | None = None
    imageUrl: str | None = None
    detail: str | None = None


class SionnaRtPocResponseDto(BaseModel):
    status: Literal["ok"]
    engine: Literal["sionna_rt"]
    plan: dict[str, Any]


def to_rf_response(result: RfRunResult) -> RfRunResponseDto:
    paths: RfRunPathsEntity | None = None
    if result.status == "succeeded" and result.paths is not None:
        p = result.paths
        paths = RfRunPathsEntity(
            output_dir=p.output_dir,
            manifest=p.manifest,
            heatmap=p.heatmap,
            summary=p.summary,
        )
    artifacts = result.artifacts if result.artifacts else None
    image_url = None
    if artifacts is not None:
        image_url = artifacts.get("imageUrl")
        if image_url is None:
            image_url = artifacts.get("visualization_path")

    return RfRunResponseDto(
        rf_run_id=result.rf_run_id,
        status=result.status,
        metrics=result.metrics,
        artifacts=artifacts,
        output_root=result.output_root or None,
        paths=paths,
        imageUrl=image_url,
        detail=result.error,
    )


