from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class RadioMaterialId(StrEnum):
    """기본 material id 집합. geometry 객체의 material_id가 이 값을 참조한다."""

    CONCRETE = "concrete"
    GLASS = "glass"
    WOOD = "wood"
    METAL = "metal"
    PLASTERBOARD = "plasterboard"
    UNKNOWN = "unknown"


class RadioMaterial(BaseModel):
    """전파 상호작용 특성을 갖는 material 정의.

    `sionna_material_key`는 Sionna ITU material 테이블의 이름이고,
    geometry 측은 이 키를 알 필요가 없다 (adapter가 해석).

    학습/보정 확장 필드 (현재 Sionna runtime에는 아직 적용되지 않으며 metadata로만 전달된다):
    - attenuation_scale: 통과 손실 보정 계수 (1.0 = 보정 없음)
    - loss_offset_db: RSSI 추가 오프셋 (dB)
    - learnable: 추후 differentiable optimization 대상 여부

    이 세 필드는 RSSI calibration / material parameter tuning을 위한 placeholder로,
    실제 runtime은 `sionna_material_key` 와 wall `thickness_m` 만 사용해
    `ITURadioMaterial` 을 생성한다. 후속 PR에서 calibration 단계가 추가될 때 적용 예정.
    """

    id: str
    name: str
    relative_permittivity: float | None = None
    conductivity: float | None = None
    scattering_coefficient: float | None = None
    sionna_material_key: str

    attenuation_scale: float = Field(default=1.0, gt=0.0)
    loss_offset_db: float = 0.0
    learnable: bool = False


DEFAULT_RADIO_MATERIALS: tuple[RadioMaterial, ...] = (
    RadioMaterial(
        id=RadioMaterialId.CONCRETE,
        name="Concrete",
        sionna_material_key="concrete",
    ),
    RadioMaterial(
        id=RadioMaterialId.GLASS,
        name="Glass",
        sionna_material_key="glass",
    ),
    RadioMaterial(
        id=RadioMaterialId.WOOD,
        name="Wood",
        sionna_material_key="wood",
    ),
    RadioMaterial(
        id=RadioMaterialId.METAL,
        name="Metal",
        sionna_material_key="metal",
    ),
    RadioMaterial(
        id=RadioMaterialId.PLASTERBOARD,
        name="Plasterboard",
        sionna_material_key="plasterboard",
    ),
    RadioMaterial(
        id=RadioMaterialId.UNKNOWN,
        name="Unknown",
        sionna_material_key="plasterboard",
    ),
)


def radio_material_table(
    materials: tuple[RadioMaterial, ...] | list[RadioMaterial] | None = None,
) -> dict[str, RadioMaterial]:
    items = materials if materials is not None else DEFAULT_RADIO_MATERIALS
    return {m.id: m for m in items}
