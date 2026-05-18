from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.entities.geometry import FloorScene
from app.domain.entities.radio import (
    AccessPoint,
    AntennaConfig,
    CorrectionProfile,
    MeasurementPlane,
    RadioMaterial,
    SceneDefaults,
    SimulationConfig,
    VisualizationConfig,
)


class SionnaRunRequestDto(BaseModel):
    """`/sionna/run` 요청 페이로드.

    Config 우선순위 (높음→낮음):
      1. 이 요청의 sub-config 필드 (simulation/scene_defaults/antenna/visualization/materials)
      2. correction_profile
      3. app defaults (도메인 Pydantic Field defaults)

    모두 optional 이며 omit 시 다음 layer로 fallback. backend는 모델 재배포 없이 이 요청
    config 만 바꿔서 다른 결과를 만들 수 있다.
    """

    engine: Literal["sionna_rt"] = "sionna_rt"
    run_type: str = "run"
    floor_id: str | None = None

    scene: FloorScene
    access_point: AccessPoint
    measurement_plane: MeasurementPlane

    # Layer 1 — request overrides
    simulation: SimulationConfig | None = None
    scene_defaults: SceneDefaults | None = None
    antenna: AntennaConfig | None = None
    visualization: VisualizationConfig | None = None
    materials: list[RadioMaterial] | None = None

    # Layer 2 — correction profile (보통 floor/project 단위 보정값)
    correction_profile: CorrectionProfile | None = None
