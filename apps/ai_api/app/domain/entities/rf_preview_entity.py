from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class RfRunPathsEntity(BaseModel):
    output_dir: str
    manifest: str
    heatmap: str | None = None
    summary: str


class InputSionnaPayloadEntity(BaseModel):
    kind: Literal["sionna_dto"] = "sionna_dto"
    data: dict[str, Any]
