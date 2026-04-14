"""
Floorplan handoff DTO (혜승 백엔드 `backend/app/schemas/floorplan.py`와 동일 계약).

- 좌표: **floor-local meter** (`units` == `"m"` 확정 후에만 RF로 전달).
- `role`: `inner` | `outer` 만 허용.
- `material`: 팀 합의 enum (`schemas/backend_scene_schema.json` 과 동일).
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


class SceneSchema(BaseModel):
    scene_version: str
    units: Literal["m"] = "m"
    sourceType: str = "floorplan"
    scale_ratio: float = 1.0
    walls: List[Wall]
    openings: List[Opening]
    rooms: List[Room] = Field(default_factory=list)
    objects: List[Any] = Field(default_factory=list)
    topology: Optional[dict[str, Any]] = None
