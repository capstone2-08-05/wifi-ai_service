from __future__ import annotations

from pydantic import BaseModel, Field


class SceneDefaults(BaseModel):
    """Scene 객체에 명시되지 않은 값의 기본치.

    - floor: 도면에 floor object가 없을 때 자동 생성되는 바닥 plate의 material/thickness.
    - default_wall_*: WallObject에 명시되지 않은 경우의 기본 — 현재 WallObject는 두 값을 모두
      필수로 받으므로 직접 사용되진 않지만, 향후 partial scene 입력 또는 외부 import 시 fallback.
    - furniture_default_thickness_m: FurnitureObject.radio_thickness_m 이 None일 때 사용.
    """

    floor_material_id: str = "concrete"
    floor_thickness_m: float = Field(default=0.05, gt=0.0)
    default_wall_height_m: float = Field(default=2.6, gt=0.0)
    default_wall_thickness_m: float = Field(default=0.12, gt=0.0)
    furniture_default_thickness_m: float = Field(default=0.1, gt=0.0)
