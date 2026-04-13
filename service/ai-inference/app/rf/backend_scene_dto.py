"""
백엔드에서 내려주는 RF 연동용 Pydantic DTO (합의 스키마).

`scene_to_rf_adapter`가 이 구조를 RF canonical dict(`RF_SCENE_HANDOFF_SPEC.md`)로 변환한다.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

WallMaterial = Literal["concrete", "glass", "wood", "metal", "unknown"]
WallRole = Literal["outer", "inner"]


class Wall(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 0.2
    height: float = 2.5
    role: WallRole = "inner"
    material: WallMaterial = "unknown"


class Opening(BaseModel):
    id: str
    type: str
    x1: float
    y1: float
    x2: float
    y2: float
    wall_ref: Optional[str] = None


class Room(BaseModel):
    id: str
    points: List[List[float]]
    center: List[float]
    area: float


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


class SceneSchema(BaseModel):
    scene_version: str = "1.0.0"
    units: str = "m"
    sourceType: str = "ai_vision"
    scale_ratio: float = 1.0
    walls: List[Wall]
    openings: List[Opening]
    rooms: List[Room] = Field(default_factory=list)
    topology: Optional[Topology] = None
    objects: List[Any] = Field(default_factory=list)


class SionnaInputDTO(BaseModel):
    config: SimConfigDTO
    antenna: AntennaDTO
    scene: SceneSchema
