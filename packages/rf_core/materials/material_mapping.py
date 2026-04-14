"""
백엔드 벽 `material` enum ↔ RF 손실 ↔ Sionna ITU 재질 매핑 (단일 진입점).

- 스키마 enum: `concrete` | `glass` | `wood` | `metal` | `unknown`.
- 레거시 문자열(`drywall` 등)은 enum으로 **정규화** 후 동일 의미 체계를 쓴다.
- 상세: `docs/RF_MATERIAL_AND_OPENING_RULES.md`.
"""

from __future__ import annotations

from typing import Final

from packages.rf_core.materials.rf_materials import BACKEND_SCHEMA_WALL_MATERIALS, MaterialProfileRegistry

# wall material enum 키 → Sionna/ITU RadioMaterial 이름
WALL_TO_SIONNA_ITU: Final[dict[str, str]] = {
    "concrete": "concrete",
    "glass": "glass",
    "wood": "wood",
    "metal": "metal",
    "unknown": "plasterboard",
}

# 백엔드 enum에 없는 **원문 키**만 ITU로 직접 매핑 (brick 등). `drywall` 은 여기 넣지 않음 → 정규화로 `wood` 처리.
LEGACY_EXTRA_TO_SIONNA_ITU: Final[dict[str, str]] = {
    "brick": "brick",
    "marble": "marble",
    "chipboard": "chipboard",
    "floorboard": "floorboard",
    "ceiling_board": "ceiling_board",
}


def normalize_wall_material_key(raw: str) -> str:
    """
    임의 입력을 **스키마 enum 문자열**로 맞춘다.

    - 공백 제거·소문자화 후 매칭.
    - ``drywall`` / ``gypsum`` → ``wood`` (경량 내벽 티어; 백엔드 enum에 drywall 없음).
    - ``plasterboard`` 원문은 ITU 이름과 혼동되므로 내부 wall 키는 ``wood``로 맞춘다.
    - 스키마에 없으면 ``unknown``.
    """
    if not isinstance(raw, str):
        return "unknown"
    s = raw.strip().lower()
    if not s:
        return "unknown"
    if s in ("drywall", "gypsum"):
        return "wood"
    if s == "plasterboard":
        return "wood"
    if s in BACKEND_SCHEMA_WALL_MATERIALS:
        return s
    return "unknown"


def get_wall_loss_db(
    material_key: str,
    *,
    registry: MaterialProfileRegistry | None = None,
) -> float:
    """한 벽 교차 1회당 가산 dB (`MaterialProfileRegistry`, 정규화 키 기준)."""
    reg = registry or MaterialProfileRegistry()
    return reg.get_loss_db(material_key)


def map_wall_material_to_sionna_itur(
    wall_material_key: str,
    *,
    table: dict[str, str] | None = None,
) -> str:
    """
    벽 재질 키 → Sionna ITU 재질 이름.

    1. 원문(소문자)이 `LEGACY_EXTRA_TO_SIONNA_ITU` 에 있으면 그 ITU 문자열 사용.
    2. 아니면 `normalize_wall_material_key` 후 `WALL_TO_SIONNA_ITU` 조회.
    3. 없으면 ``plasterboard``.
    """
    merged_extra = {**LEGACY_EXTRA_TO_SIONNA_ITU, **(table or {})}
    k = wall_material_key.strip() if isinstance(wall_material_key, str) else str(wall_material_key)
    kl = k.lower()
    if kl in merged_extra:
        return merged_extra[kl]
    kn = normalize_wall_material_key(k)
    return WALL_TO_SIONNA_ITU.get(kn, "plasterboard")


DEFAULT_WALL_MATERIAL_TO_SIONNA_ITU: Final[dict[str, str]] = {
    **WALL_TO_SIONNA_ITU,
    **LEGACY_EXTRA_TO_SIONNA_ITU,
    "drywall": "plasterboard",
}
