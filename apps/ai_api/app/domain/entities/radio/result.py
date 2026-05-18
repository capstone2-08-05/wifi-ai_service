from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities.geometry.scene import SceneBounds
from app.domain.entities.radio.simulation_config import SimulationConfig


class RssiSummary(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None


class CoverageSummary(BaseModel):
    ge_minus_67: float = Field(..., alias="ge_-67")
    ge_minus_70: float = Field(..., alias="ge_-70")
    ge_minus_75: float = Field(..., alias="ge_-75")
    valid_cell_count: int
    total_cell_count: int
    valid_cell_ratio: float

    model_config = {"populate_by_name": True}


class RadioMapResult(BaseModel):
    """Sionna RT 실행 결과의 도메인 표현. infrastructure에서 채워서 반환."""

    grid_shape: tuple[int, int]
    bounds_m: SceneBounds
    measurement_plane_z_m: float
    values_dbm: list[list[float]]
    valid_cell_count: int
    invalid_cell_count: int
    valid_cell_ratio: float
    rssi: RssiSummary
    coverage: CoverageSummary
    config: SimulationConfig
