from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


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
        description="High attenuation exterior or structural wall",
    ),
    "glass": MaterialProfile(
        name="glass",
        freq_ghz=5.0,
        attenuation_db=6.0,
        description="Medium attenuation transparent surface",
    ),
    "drywall": MaterialProfile(
        name="drywall",
        freq_ghz=5.0,
        attenuation_db=4.0,
        description="Low attenuation lightweight partition",
    ),
    "wood": MaterialProfile(
        name="wood",
        freq_ghz=5.0,
        attenuation_db=5.0,
        description="Medium attenuation wooden partition",
    ),
}


class MaterialProfileRegistry:
    """Lookup object so the simulator is not tied to hard-coded globals."""

    def __init__(self, profiles: Dict[str, MaterialProfile] | None = None) -> None:
        self._profiles = dict(profiles or DEFAULT_MATERIAL_PROFILES)

    def get_loss_db(self, material_name: str) -> float:
        """등록된 프로파일 키의 `attenuation_db`. 미등록 키는 **0 dB** (합산에서 무시).

        Baseline은 `Scene` 파싱 후 `Wall.material` 문자열만 사용한다.
        규칙 요약: `docs/RF_MATERIAL_AND_OPENING_RULES.md`.
        """
        profile = self._profiles.get(material_name)
        return 0.0 if profile is None else float(profile.attenuation_db)

    def as_serializable(self) -> dict:
        return {
            name: {
                "freq_ghz": profile.freq_ghz,
                "attenuation_db": profile.attenuation_db,
                "description": profile.description,
            }
            for name, profile in self._profiles.items()
        }
