from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.entities.radio.material import RadioMaterial


class CorrectionProfile(BaseModel):
    """RSSI/material 측정 기반 보정 프로필.

    request 보다 낮고 app defaults 보다 높은 우선순위 layer. 같은 layer 안에서:
    - materials: material_id 별 RadioMaterial override (calibration field 채워서 보냄)
    - physical/propagation/solver/scene_defaults/antenna/visualization 도 부분 override 가능

    backend는 floor/project 단위로 이 profile을 가지고 있다가 요청 시점에 함께 보낸다 — 모델
    재배포 없이 백엔드 데이터만 바꿔 다른 결과를 만들 수 있는 핵심 진입점.
    """

    id: str | None = None
    name: str | None = None
    materials: dict[str, RadioMaterial] = Field(default_factory=dict)
    # 부분 override를 위해 sub-config는 dict 형태로 받음 (Pydantic으로 layer마다 풀 인스턴스를
    # 요구하면 부분 override가 표현이 안 됨). resolver가 merge.
    physical_overrides: dict = Field(default_factory=dict)
    propagation_overrides: dict = Field(default_factory=dict)
    solver_overrides: dict = Field(default_factory=dict)
    scene_defaults_overrides: dict = Field(default_factory=dict)
    antenna_overrides: dict = Field(default_factory=dict)
    visualization_overrides: dict = Field(default_factory=dict)
