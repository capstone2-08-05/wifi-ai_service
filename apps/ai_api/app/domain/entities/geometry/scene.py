from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.domain.entities.geometry.furniture import FurnitureObject
from app.domain.entities.geometry.opening import OpeningObject
from app.domain.entities.geometry.room import RoomObject
from app.domain.entities.geometry.wall import WallObject


class SceneBounds(BaseModel):
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @model_validator(mode="after")
    def _validate_extent(self) -> "SceneBounds":
        if self.max_x <= self.min_x or self.max_y <= self.min_y:
            raise ValueError("scene bounds must have positive extent")
        return self

    def contains_xy(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


class FloorScene(BaseModel):
    scene_id: str | None = None
    walls: list[WallObject] = Field(default_factory=list)
    openings: list[OpeningObject] = Field(default_factory=list)
    rooms: list[RoomObject] = Field(default_factory=list)
    furniture: list[FurnitureObject] = Field(default_factory=list)
    bounds: SceneBounds | None = None

    @model_validator(mode="after")
    def _validate_opening_wall_refs(self) -> "FloorScene":
        if not self.openings:
            return self
        wall_ids = {w.id for w in self.walls}
        for opening in self.openings:
            if opening.wall_id not in wall_ids:
                raise ValueError(
                    f"opening {opening.id} references unknown wall_id {opening.wall_id}"
                )
        return self

    def compute_bounds(self, *, pad_m: float = 0.5) -> SceneBounds:
        xs: list[float] = []
        ys: list[float] = []
        for wall in self.walls:
            xs.extend([wall.start_xy[0], wall.end_xy[0]])
            ys.extend([wall.start_xy[1], wall.end_xy[1]])
        for room in self.rooms:
            for x, y in room.polygon_xy:
                xs.append(x)
                ys.append(y)
        for piece in self.furniture:
            for x, y in piece.polygon_xy:
                xs.append(x)
                ys.append(y)
        if not xs or not ys:
            raise ValueError("cannot compute bounds: scene has no spatial elements")
        return SceneBounds(
            min_x=min(xs) - pad_m,
            max_x=max(xs) + pad_m,
            min_y=min(ys) - pad_m,
            max_y=max(ys) + pad_m,
        )
