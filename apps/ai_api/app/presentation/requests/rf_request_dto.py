from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.entities.rf_preview_entity import (
    InputSionnaPayloadEntity,
)


class RfRunRequestDto(BaseModel):
    engine: Literal["sionna_rt"] = "sionna_rt"
    run_type: str = "preview"
    floor_id: str | None = None
    input: InputSionnaPayloadEntity
