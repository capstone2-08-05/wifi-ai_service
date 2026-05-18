from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities.geometry.scene import SceneBounds


class MeasurementPlane(BaseModel):
    """Radio map을 평가할 수평면. bounds는 명시되지 않으면 scene bounds로부터 유도."""

    z_m: float = Field(..., gt=0.0)
    cell_size_m: float = Field(..., gt=0.0)
    bounds: SceneBounds | None = None
