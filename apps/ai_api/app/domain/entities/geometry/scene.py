from __future__ import annotations

import math

from pydantic import BaseModel, Field, model_validator

from app.domain.entities.geometry.furniture import FurnitureObject
from app.domain.entities.geometry.opening import OpeningObject
from app.domain.entities.geometry.room import RoomObject
from app.domain.entities.geometry.wall import WallObject

# 검증 시 허용 오차 (centimeter 수준)
_OPENING_PERP_TOLERANCE_M = 0.01
_OPENING_FIT_TOLERANCE_M = 0.01
_OPENING_OVERLAP_TOLERANCE_M = 1e-6


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

    @model_validator(mode="after")
    def _validate_opening_placement(self) -> "FloorScene":
        """Opening center가 wall 위에 있는지, width가 wall 길이에 들어가는지, 같은 wall 위에서
        opening끼리 겹치지 않는지 검증. Sionna mesh split 단계가 가정하는 조건이 여기서 보장된다.
        """
        if not self.openings:
            return self
        walls_by_id = {w.id: w for w in self.walls}

        openings_by_wall: dict[str, list[OpeningObject]] = {}
        for op in self.openings:
            openings_by_wall.setdefault(op.wall_id, []).append(op)

        for wall_id, ops in openings_by_wall.items():
            wall = walls_by_id[wall_id]
            x1, y1 = wall.start_xy
            x2, y2 = wall.end_xy
            dx, dy = x2 - x1, y2 - y1
            wall_length = math.hypot(dx, dy)
            if wall_length <= 1e-9:
                continue  # degenerate wall — 별도 validator가 잡음

            intervals: list[tuple[float, float, str]] = []
            for op in ops:
                cx, cy = op.center_xy
                t = ((cx - x1) * dx + (cy - y1) * dy) / (wall_length * wall_length)
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                perp = math.hypot(cx - proj_x, cy - proj_y)
                if perp > _OPENING_PERP_TOLERANCE_M:
                    raise ValueError(
                        f"opening {op.id} center is {perp:.3f}m off wall {wall_id} axis"
                    )
                s_center = t * wall_length
                half = op.width_m / 2.0
                s_start = s_center - half
                s_end = s_center + half
                if (
                    s_start < -_OPENING_FIT_TOLERANCE_M
                    or s_end > wall_length + _OPENING_FIT_TOLERANCE_M
                ):
                    raise ValueError(
                        f"opening {op.id} (along-wall [{s_start:.3f}, {s_end:.3f}]m) "
                        f"does not fit within wall {wall_id} length {wall_length:.3f}m"
                    )
                intervals.append((s_start, s_end, op.id))

            intervals.sort()
            for i in range(len(intervals) - 1):
                if intervals[i][1] > intervals[i + 1][0] + _OPENING_OVERLAP_TOLERANCE_M:
                    raise ValueError(
                        f"openings {intervals[i][2]} and {intervals[i + 1][2]} "
                        f"overlap on wall {wall_id}"
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
