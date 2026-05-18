from __future__ import annotations

from pydantic import BaseModel, Field


class AccessPoint(BaseModel):
    """AP 송신기. tx_power_dbm/frequency_ghz는 SimulationConfig로 옮기지 않고
    AP 단위로 가질 수 있도록 별도로 둔다 (멀티 AP/이종 AP 시나리오 대비).

    물리 파라미터로 분류 — 결과 의미를 바꾸는 값.
    """

    id: str
    position_m: tuple[float, float, float]
    tx_power_dbm: float | None = None
    frequency_ghz: float | None = None
    name: str | None = None

    @property
    def x(self) -> float:
        return self.position_m[0]

    @property
    def y(self) -> float:
        return self.position_m[1]

    @property
    def z(self) -> float:
        return self.position_m[2]
