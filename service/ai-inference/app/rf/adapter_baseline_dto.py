"""
백엔드 `SionnaInputDTO` / `SceneSchema` → **Baseline RF** 입력.

- 기하: **2D floorplan만** (벽·개구·방은 x, y). 벽 `height`는 baseline 규칙상 손실 모델에 쓰이지 않더라도 스키마 호환을 위해 유지.
- 안테나: 기본적으로 **수평 위치만** 사용하고, ``z``는 `z_policy`로 선택 (무시 시 `default_z_m`).

Sionna(3D·ITU 재질) 경로는 `adapter_sionna_dto.py`.
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Mapping

from backend_scene_dto import AntennaDTO
from backend_scene_dto import SceneSchema as BackendSceneSchema
from backend_scene_dto import SimConfigDTO
from backend_scene_dto import SionnaInputDTO

from scene_to_rf_adapter import (  # noqa: PLC0415 — 동일 패키지 공용 헬퍼
    _backend_opening_to_rf,
    _backend_room_to_rf,
    _normalize_wall,
)


def scene_schema_to_baseline_rf_scene_dict(
    scene: BackendSceneSchema | Mapping[str, Any],
    *,
    floor_id: str | None = None,
    material_id_to_profile_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Baseline 전용: `SceneSchema` → `rf_models.Scene` 호환 루트 dict.

    벽/개구/방은 **x,y 평면** 기준으로만 의미를 둔다 (DTO z 없음).
    """
    if not isinstance(scene, BackendSceneSchema):
        scene = BackendSceneSchema.model_validate(scene)

    if scene.units != "m":
        raise ValueError("Backend SceneSchema.units must be 'm' for RF scene input")

    scene_version_id = scene.scene_version.strip() if scene.scene_version else "unknown"

    walls_out: list[dict[str, Any]] = []
    for w in scene.walls:
        raw = w.model_dump()
        walls_out.append(_normalize_wall(raw, material_id_to_profile_key=material_id_to_profile_key))

    openings_out: list[dict[str, Any]] = []
    for o in scene.openings:
        openings_out.append(_backend_opening_to_rf(o, scene_version_id=scene_version_id))

    rooms_out: list[dict[str, Any]] = []
    for r in scene.rooms:
        rooms_out.append(_backend_room_to_rf(r, scene_version_id=scene_version_id))

    objects: list[Any] = []
    for i, o in enumerate(scene.objects):
        if isinstance(o, dict):
            objects.append(copy.deepcopy(o))
        else:
            raise TypeError(f"scene.objects[{i}] must be a dict for RF Scene")

    out: dict[str, Any] = {
        "units": "m",
        "sourceType": scene.sourceType.strip() if scene.sourceType else "unknown",
        "scene_version_id": scene_version_id,
        "walls": walls_out,
        "openings": openings_out,
        "rooms": rooms_out,
        "objects": objects,
    }
    if floor_id is not None and floor_id.strip():
        out["floor_id"] = floor_id.strip()
    return out


def antenna_dto_to_baseline_ap_layout_dict(
    antenna: AntennaDTO | Mapping[str, Any],
    *,
    scene_version_id: str,
    sim_config: SimConfigDTO | Mapping[str, Any] | None = None,
    layout_name: str = "manual_single",
    layout_type: str = "manual",
    z_policy: Literal["ignore", "use_position_z"] = "ignore",
    default_z_m: float = 2.5,
) -> dict[str, Any]:
    """
    Baseline 전용 `ApLayout` dict.

    - **ignore:** ``point_geom`` 은 (x,y)만 쓰고 ``z_m`` 은 ``default_z_m`` (2D preview에 맞춤).
    - **use_position_z:** ``position_m[2]`` 를 ``z_m`` 에 넣어 링크예산 등 **참고**용으로 사용.
    """
    if not isinstance(antenna, AntennaDTO):
        antenna = AntennaDTO.model_validate(antenna)
    cfg = sim_config
    if cfg is None:
        cfg_d = SimConfigDTO()
    elif isinstance(cfg, SimConfigDTO):
        cfg_d = cfg
    else:
        cfg_d = SimConfigDTO.model_validate(cfg)

    pos = antenna.position_m
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        raise ValueError("AntennaDTO.position_m must include at least [x, y] in meters")

    if z_policy == "use_position_z" and len(pos) < 3:
        raise ValueError("z_policy=use_position_z requires position_m [x, y, z]")

    z_m = float(pos[2]) if z_policy == "use_position_z" else float(default_z_m)

    tx_id = antenna.tx_id.strip() if isinstance(antenna.tx_id, str) else str(antenna.tx_id)
    return {
        "scene_version_id": scene_version_id.strip(),
        "layout_name": layout_name,
        "layout_type": layout_type,
        "aps": [
            {
                "id": tx_id,
                "ap_name": tx_id,
                "point_geom": {
                    "type": "Point",
                    "coordinates": [float(pos[0]), float(pos[1])],
                },
                "z_m": z_m,
                "tx_power_dbm": float(cfg_d.tx_power_dbm),
                "frequency_ghz": float(cfg_d.frequency_ghz),
                "azimuth_deg": 0.0,
                "tilt_deg": 0.0,
            }
        ],
    }


def sionna_input_dto_to_baseline_scene_and_layout(
    payload: SionnaInputDTO | Mapping[str, Any],
    *,
    floor_id: str | None = None,
    material_id_to_profile_key: dict[str, str] | None = None,
    layout_name: str = "manual_single",
    layout_type: str = "manual",
    antenna_z_policy: Literal["ignore", "use_position_z"] = "ignore",
    default_antenna_z_m: float = 2.5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Baseline 한 세트: (RF scene dict, 수동 AP layout)."""
    dto = payload if isinstance(payload, SionnaInputDTO) else SionnaInputDTO.model_validate(payload)
    scene_dict = scene_schema_to_baseline_rf_scene_dict(
        dto.scene,
        floor_id=floor_id,
        material_id_to_profile_key=material_id_to_profile_key,
    )
    layout_dict = antenna_dto_to_baseline_ap_layout_dict(
        dto.antenna,
        scene_version_id=scene_dict["scene_version_id"],
        sim_config=dto.config,
        layout_name=layout_name,
        layout_type=layout_type,
        z_policy=antenna_z_policy,
        default_z_m=default_antenna_z_m,
    )
    return scene_dict, layout_dict
