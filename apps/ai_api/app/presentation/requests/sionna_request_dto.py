from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.entities.geometry import FloorScene
from app.domain.entities.radio import (
    AccessPoint,
    MeasurementPlane,
    RadioMaterial,
    SimulationConfig,
)


class SionnaRunRequestDto(BaseModel):
    """`/sionna/run` 요청 페이로드.

    이전에는 `input.data: dict[str, Any]`로 무엇이든 받고 infrastructure까지 흘려보냈으나,
    이제 presentation 경계에서 domain object로 강하게 검증한다.
    잘못된 payload는 FastAPI가 422로 거절한다.
    """

    engine: Literal["sionna_rt"] = "sionna_rt"
    run_type: str = "run"
    floor_id: str | None = None

    scene: FloorScene
    access_point: AccessPoint
    measurement_plane: MeasurementPlane
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    materials: list[RadioMaterial] | None = None
