from __future__ import annotations

from pydantic import BaseModel, model_validator


class RoomObject(BaseModel):
    id: str
    polygon_xy: list[tuple[float, float]]
    name: str | None = None

    @model_validator(mode="after")
    def _validate_polygon(self) -> "RoomObject":
        if len(self.polygon_xy) < 3:
            raise ValueError(f"room {self.id} polygon must have at least 3 points")
        return self
