from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet

# 백엔드 Scene JSON 스키마(`schemas/backend_scene_schema.json`)와 동일 enum
BACKEND_SCHEMA_WALL_MATERIALS: FrozenSet[str] = frozenset(
    ("concrete", "glass", "wood", "metal", "unknown")
)


@dataclass(frozen=True)
class MaterialProfile:
    """Simple RF attenuation profile used by the baseline simulator."""

    name: str
    freq_ghz: float
    attenuation_db: float
    description: str


DEFAULT_MATERIAL_PROFILES: Dict[str, MaterialProfile] = {
    "concrete": MaterialProfile(
        name="concrete",
        freq_ghz=5.0,
        attenuation_db=12.0,
        description="Structural / heavy wall (schema default high loss)",
    ),
    "glass": MaterialProfile(
        name="glass",
        freq_ghz=5.0,
        attenuation_db=6.0,
        description="Glazing / transparent surface",
    ),
    "wood": MaterialProfile(
        name="wood",
        freq_ghz=5.0,
        attenuation_db=5.0,
        description="Wooden partition",
    ),
    "metal": MaterialProfile(
        name="metal",
        freq_ghz=5.0,
        attenuation_db=18.0,
        description="High attenuation metal structure",
    ),
    "unknown": MaterialProfile(
        name="unknown",
        freq_ghz=5.0,
        attenuation_db=4.0,
        description="Fallback when material is unspecified or low confidence",
    ),
}


class MaterialProfileRegistry:
    """Lookup object so the simulator is not tied to hard-coded globals."""

    def __init__(self, profiles: Dict[str, MaterialProfile] | None = None) -> None:
        self._profiles = dict(profiles or DEFAULT_MATERIAL_PROFILES)

    def get_loss_db(self, material_name: str) -> float:
        """등록된 프로파일 키의 `attenuation_db`. 미등록 키는 ``unknown`` 과 동일 손실로 폴백.

        Baseline은 `Scene` 파싱 후 `Wall.material` 문자열만 사용한다.
        조회 전 `material_mapping.normalize_wall_material_key` 로 enum 키로 맞춘다.
        규칙 요약: `docs/RF_MATERIAL_AND_OPENING_RULES.md`.
        """
        from material_mapping import normalize_wall_material_key  # noqa: PLC0415

        key = normalize_wall_material_key(material_name)
        profile = self._profiles.get(key)
        if profile is not None:
            return float(profile.attenuation_db)
        fallback = self._profiles.get("unknown")
        return float(fallback.attenuation_db) if fallback is not None else 4.0

    def as_serializable(self) -> dict:
        return {
            name: {
                "freq_ghz": profile.freq_ghz,
                "attenuation_db": profile.attenuation_db,
                "description": profile.description,
            }
            for name, profile in self._profiles.items()
        }
