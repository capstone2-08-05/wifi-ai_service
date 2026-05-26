"""ai_api 도메인의 SimulationConfig.

⚠️ web-platform 경로에서의 source of truth 는 여기가 아님:
   `web-platform/backend/app/core/rf_defaults.py`

web-platform 의 `rf_backend_local._build_sionna_request_payload` 가 모든 sub-config
(physical / solver / propagation) 를 명시적으로 채워서 보내므로 이 모듈의 Field default
는 사용되지 않는다. 단, ai_api `/internal/sionna/run` 을 직접 호출하는 다른 클라이언트
(테스트/CLI 등) 에선 fallback 으로 동작. 혼선 방지 위해 rf_defaults.py 와 **같은 값** 유지.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PhysicalConfig(BaseModel):
    """결과의 물리적 의미를 결정하는 값. RSSI 보정/material 학습 시 변경 가능.

    - tx_power_offset_db: 모든 TX 의 송신 전력에 더해지는 전역 보정. 측정값-시뮬값 mismatch
      를 단순히 평행이동으로 맞출 때 사용. runtime이 `tx_power_dbm += tx_power_offset_db` 로
      적용.
    """

    frequency_ghz: float = Field(default=5.0, gt=0.0)
    tx_power_dbm: float = 20.0
    tx_power_offset_db: float = 0.0


class PropagationConfig(BaseModel):
    """어떤 전파 메커니즘을 켤지. 켜고 끄는 것 자체가 결과 의미를 바꾼다."""

    los: bool = True
    specular_reflection: bool = True
    refraction: bool = True
    diffuse_reflection: bool = True
    diffraction: bool = True


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
