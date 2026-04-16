from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from app.domain.entities.rf_preview_entity import RfRunPathsEntity


class RfRunResponseDto(BaseModel):
    rf_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    output_root: str | None = None
    paths: RfRunPathsEntity | None = None
    imageUrl: str | None = None
    detail: str | None = None


def to_rf_response(result: dict[str, Any]) -> RfRunResponseDto:
    paths: RfRunPathsEntity | None = None
    raw_paths = result.get("paths")
    if result.get("status") == "succeeded" and isinstance(raw_paths, dict):
        p = raw_paths
        paths = RfRunPathsEntity(
            output_dir=str(p.get("output_dir", "")),
            manifest=str(p.get("manifest", "")),
            heatmap=p.get("heatmap"),
            summary=str(p.get("summary", "")),
        )
    artifacts = result.get("artifacts") or None
    image_url = None
    if artifacts is not None:
        image_url = artifacts.get("imageUrl")
        if image_url is None:
            image_url = artifacts.get("visualization_path")

    return RfRunResponseDto(
        rf_run_id=str(result.get("rf_run_id", "")),
        status=str(result.get("status", "failed")),
        metrics=result.get("metrics"),
        artifacts=artifacts,
        output_root=result.get("output_root") or None,
        paths=paths,
        imageUrl=image_url,
        detail=result.get("error"),
    )
