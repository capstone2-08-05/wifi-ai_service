from __future__ import annotations

from pydantic import BaseModel, Field


class PhysicalConfig(BaseModel):
    """결과의 물리적 의미를 결정하는 값. RSSI 보정/material 학습 시 변경 가능."""

    frequency_ghz: float = Field(default=5.0, gt=0.0)
    tx_power_dbm: float = 20.0


class PropagationConfig(BaseModel):
    """어떤 전파 메커니즘을 켤지. 켜고 끄는 것 자체가 결과 의미를 바꾼다."""

    los: bool = True
    specular_reflection: bool = True
    refraction: bool = True
    diffuse_reflection: bool = False
    diffraction: bool = False


class SolverConfig(BaseModel):
    """계산 품질/성능을 결정하는 값. 물리적 의미가 아니라 근사 정밀도에 가깝다."""

    max_depth: int = Field(default=5, ge=0)
    samples_per_tx: int = Field(default=500_000, gt=0)
    seed: int = 42


class SimulationConfig(BaseModel):
    """물리 / 전파 메커니즘 / solver 설정을 한 곳에서 묶어 전달.

    위의 세 sub-config는 각각 다른 이유로 바뀌므로 분리되어 있다:
    - PhysicalConfig: 결과의 물리적 의미
    - PropagationConfig: 어떤 전파 메커니즘을 모델링할지
    - SolverConfig: 계산 정밀도/성능
    """

    physical: PhysicalConfig = Field(default_factory=PhysicalConfig)
    propagation: PropagationConfig = Field(default_factory=PropagationConfig)
    solver: SolverConfig = Field(default_factory=SolverConfig)
