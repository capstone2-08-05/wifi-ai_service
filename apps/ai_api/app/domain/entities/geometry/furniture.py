from __future__ import annotations

from pydantic import BaseModel, Field


class FurnitureObject(BaseModel):
    id: str
    polygon_xy: list[tuple[float, float]]
    height_m: float = Field(..., gt=0.0)
    material_id: str
    name: str | None = None
