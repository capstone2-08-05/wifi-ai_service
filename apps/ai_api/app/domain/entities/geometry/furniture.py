from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class FurnitureObject(BaseModel):
    id: str
    polygon_xy: list[tuple[float, float]]
    height_m: float = Field(..., gt=0.0)
    material_id: str
    name: str | None = None

    @model_validator(mode="after")
    def _validate_polygon(self) -> "FurnitureObject":
        if len(self.polygon_xy) < 3:
            raise ValueError(
                f"furniture {self.id} polygon must have at least 3 points"
            )
        return self
