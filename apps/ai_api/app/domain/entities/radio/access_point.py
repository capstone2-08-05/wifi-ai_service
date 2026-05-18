from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AccessPoint(BaseModel):
    """AP 송신기. tx_power_dbm/frequency_ghz는 SimulationConfig로 옮기지 않고
    AP 단위로 가질 수 있도록 별도로 둔다 (멀티 AP/이종 AP 시나리오 대비).

    물리 파라미터로 분류 — 결과 의미를 바꾸는 값.
    """

    id: str
    position_m: tuple[float, float, float]
    tx_power_dbm: float | None = Field(default=None, ge=-100.0, le=60.0)
    frequency_ghz: float | None = Field(default=None, gt=0.0)
    name: str | None = None

    @field_validator("position_m")
    @classmethod
    def _validate_position(cls, v: tuple[float, float, float]) -> tuple[float, float, float]:
        if v[2] < 0.0:
            raise ValueError(f"AP z_m must be >= 0, got {v[2]}")
        return v

    @property
    def x(self) -> float:
        return self.position_m[0]

    @property
    def y(self) -> float:
        return self.position_m[1]

    @property
    def z(self) -> float:
        return self.position_m[2]
