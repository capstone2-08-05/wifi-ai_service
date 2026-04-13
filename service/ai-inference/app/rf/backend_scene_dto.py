"""
백엔드에서 내려주는 RF 연동용 DTO.

씬 그래프(`SceneSchema`, `Wall`, `Opening`, `Room`)는 ``app.schemas.floorplan`` 에서 import 한다
(혜승 백엔드 `backend/app/schemas/floorplan.py` 와 동일 계약).

`scene_to_rf_adapter` 출력은 `rf_models.Scene` canonical dict (`docs/RF_SCENE_HANDOFF_SPEC.md`).
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.schemas.floorplan import (  # noqa: E402
    Opening,
    Room,
    SceneSchema,
    Wall,
    WallMaterial,
    WallRole,
)


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
