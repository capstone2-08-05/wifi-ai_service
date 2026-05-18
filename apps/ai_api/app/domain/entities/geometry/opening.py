from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class OpeningKind(StrEnum):
    DOOR = "door"
    WINDOW = "window"


class OpeningObject(BaseModel):
    id: str
    wall_id: str
    kind: OpeningKind
    center_xy: tuple[float, float]
    width_m: float = Field(..., gt=0.0)
    bottom_z_m: float = Field(..., ge=0.0)
    height_m: float = Field(..., gt=0.0)
    material_id: str
