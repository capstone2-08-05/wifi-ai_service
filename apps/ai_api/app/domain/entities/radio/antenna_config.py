from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AntennaConfig(BaseModel):
    """송신/수신 안테나 array 설정. 현재는 TX side에서만 사용되며 모든 AP가 공유한다.

    Sionna PlanarArray 인자에 1:1 대응. 1x1 isotropic vertical polarization은
    실내 Wi-Fi MVP 기준값으로, 다중 안테나/패턴 실험 시 변경.
    """

    array_rows: int = Field(default=1, ge=1)
    array_cols: int = Field(default=1, ge=1)
    vertical_spacing: float = Field(default=0.5, gt=0.0)
    horizontal_spacing: float = Field(default=0.5, gt=0.0)
    pattern: Literal["iso", "dipole", "hw_dipole", "tr38901"] = "iso"
    polarization: Literal["V", "H", "VH", "cross"] = "V"
