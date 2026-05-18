from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class FurnitureObject(BaseModel):
    """가구. polygon_xy를 height_m 만큼 수직 extrusion 한 prism으로 모델링된다.

    `radio_thickness_m` 은 ITURadioMaterial 의 slab thickness 로 들어가는 값으로,
    실제 가구의 평균적인 RF 통과 두께를 표현한다 (책상 상판 3cm, 책장 30cm 등).
    None 이면 SceneDefaults.furniture_default_thickness_m 가 사용된다.
    """

    id: str
    polygon_xy: list[tuple[float, float]]
    height_m: float = Field(..., gt=0.0)
    material_id: str
    radio_thickness_m: float | None = Field(default=None, gt=0.0)
    name: str | None = None

    @model_validator(mode="after")
    def _validate_polygon(self) -> "FurnitureObject":
        if len(self.polygon_xy) < 3:
            raise ValueError(
                f"furniture {self.id} polygon must have at least 3 points"
            )
        return self
