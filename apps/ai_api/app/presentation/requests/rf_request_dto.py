from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.domain.entities.rf_preview_entity import (
    BaselineParamsEntity,
    InputRfCanonicalEntity,
    InputSionnaPayloadEntity,
)


class RfRunRequestDto(BaseModel):
    engine: Literal["baseline"] = "baseline"
    run_type: str = "preview"
    floor_id: str | None = None
    baseline: BaselineParamsEntity = Field(default_factory=BaselineParamsEntity)
    input: Annotated[Union[InputSionnaPayloadEntity, InputRfCanonicalEntity], Field(discriminator="kind")]


class SionnaRtPocRequestDto(BaseModel):
    input: InputSionnaPayloadEntity
    measurement_plane_z_m: float = 1.0
    material_map: dict[str, str] | None = None


