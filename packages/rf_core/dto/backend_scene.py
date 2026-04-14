"""RF 연동 DTO — 씬 타입은 ``app.schemas.floorplan`` 과 동일 계약."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from packages.contracts.floorplan import SceneSchema


class Topology(BaseModel):
    adjacencies: List[List[str]] = Field(default_factory=list)
    connectivity: List[List[str]] = Field(default_factory=list)


class SimConfigDTO(BaseModel):
    frequency_ghz: float = 28.0
    tx_power_dbm: float = 30.0
    reflection_order: int = 2


class AntennaDTO(BaseModel):
    tx_id: str = "router_1"
    position_m: List[float] = Field(..., description="[x, y, z] 실제 미터 좌표")


class SionnaInputDTO(BaseModel):
    config: SimConfigDTO
    antenna: AntennaDTO
    scene: SceneSchema
