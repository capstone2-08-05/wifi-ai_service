from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.entities.radio.antenna_config import AntennaConfig
from app.domain.entities.radio.material import RadioMaterial
from app.domain.entities.radio.scene_defaults import SceneDefaults
from app.domain.entities.radio.simulation_config import (
    PhysicalConfig,
    PropagationConfig,
    SolverConfig,
)
from app.domain.entities.radio.visualization_config import VisualizationConfig

# 어느 layer 에서 값이 왔는지 (provenance)
ConfigSource = Literal["request", "correction_profile", "app_default"]


class ResolvedSionnaConfig(BaseModel):
    """모든 layer가 merge된 최종 실행 config.

    runtime/adapter는 이 객체만 본다 — request나 correction_profile을 직접 알지 않음.
    `provenance`는 디버깅/감사를 위한 평탄화된 dotted-path → source 매핑.
    """

    physical: PhysicalConfig
    propagation: PropagationConfig
    solver: SolverConfig
    scene_defaults: SceneDefaults
    antenna: AntennaConfig
    visualization: VisualizationConfig
    materials: dict[str, RadioMaterial]
    provenance: dict[str, ConfigSource] = Field(default_factory=dict)
