from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class WallObject(BaseModel):
    id: str
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    height_m: float = Field(..., gt=0.0)
    thickness_m: float = Field(..., gt=0.0)
    material_id: str

    @model_validator(mode="after")
    def _validate_non_degenerate(self) -> "WallObject":
        if self.start_xy == self.end_xy:
            raise ValueError(f"wall {self.id} is degenerate: start_xy == end_xy")
        return self
