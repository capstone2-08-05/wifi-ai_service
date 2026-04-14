"""
백엔드 `SionnaInputDTO` → **Sionna RT(내부 precise)** 쪽에서 쓸 계획/파라미터.

- 기하: 벽 **높이(thickness, height)**, 안테나 **(x,y,z)** 를 명시.
- 솔버: ``SimConfigDTO.reflection_order`` → 레이 최대 반사 차수(`max_depth` 등)에 매핑,
  ``frequency_ghz``, ``tx_power_dbm`` 그대로 전달.
- 재질: wall 문자열 키 → **ITU RadioMaterial 이름** (Sionna) 테이블 매핑.

실제 메시 빌드·`run_sionna_radiomap` 연결은 PoC 단계에서 별도로 두고,
여기서는 **JSON 직렬화 가능한 엔진 입력 스냅샷**을 만든다.
"""

from __future__ import annotations

from typing import Any, Mapping

from packages.rf_core.dto.backend_scene import SceneSchema as BackendSceneSchema
from packages.rf_core.dto.backend_scene import SionnaInputDTO

from packages.rf_core.materials.material_mapping import (
    DEFAULT_WALL_MATERIAL_TO_SIONNA_ITU,
    map_wall_material_to_sionna_itur,
)


def scene_schema_to_sionna_scene_plan(
    scene: BackendSceneSchema | Mapping[str, Any],
    *,
    material_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Sionna 쪽 메시/씬 빌더가 참고할 **3D 관련** 벽·개구·방 요약.

    - 벽: 중심선 2D + ``thickness_m``, ``height_m``, ``itu_material``
    - 개구: 2D 세그먼트 + ``wall_ref`` + ``opening_type``
    - 방: 2D 다각형(바닥 투영) + 면적·중심 (바닥 메시 등에 활용)
    """
    if not isinstance(scene, BackendSceneSchema):
        scene = BackendSceneSchema.model_validate(scene)

    walls: list[dict[str, Any]] = []
    for w in scene.walls:
        itu = map_wall_material_to_sionna_itur(w.material, table=material_map)
        walls.append(
            {
                "id": w.id,
                "x1": float(w.x1),
                "y1": float(w.y1),
                "x2": float(w.x2),
                "y2": float(w.y2),
                "thickness_m": float(w.thickness),
                "height_m": float(w.height),
                "role": w.role,
                "wall_material": w.material,
                "itu_radio_material": itu,
            }
        )

    openings: list[dict[str, Any]] = []
    for o in scene.openings:
        openings.append(
            {
                "id": o.id,
                "type": o.type,
                "x1": float(o.x1),
                "y1": float(o.y1),
                "x2": float(o.x2),
                "y2": float(o.y2),
                "wall_ref": o.wall_ref,
            }
        )

    rooms: list[dict[str, Any]] = []
    for r in scene.rooms:
        rooms.append(
            {
                "id": r.id,
                "points": r.points,
                "center": r.center,
                "area_m2": float(r.area),
            }
        )

    return {
        "scene_version": scene.scene_version,
        "units": scene.units,
        "sourceType": scene.sourceType,
        "scale_ratio": scene.scale_ratio,
        "walls": walls,
        "openings": openings,
        "rooms": rooms,
        "objects": list(scene.objects),
    }


def sionna_input_dto_to_engine_plan(
    payload: SionnaInputDTO | Mapping[str, Any],
    *,
    material_map: dict[str, str] | None = None,
    measurement_plane_z_m: float = 1.0,
) -> dict[str, Any]:
    """
    동일 DTO로부터 Sionna 엔진용 스냅샷(씬 계획 + 안테나 3D + 솔버 파라미터).

    - ``reflection_order`` → ``solver.max_depth`` (레이 트레이싱 깊이 상한에 대응)
    - ``measurement_plane_z_m``: RadioMap 수신 평면 높이 (UE 높이 가정), DTO에 없으면 인자 기본값
    """
    dto = payload if isinstance(payload, SionnaInputDTO) else SionnaInputDTO.model_validate(payload)
    cfg = dto.config
    ant = dto.antenna
    pos = ant.position_m
    if not isinstance(pos, (list, tuple)) or len(pos) < 3:
        raise ValueError("Sionna path requires AntennaDTO.position_m [x, y, z]")

    scene_plan = scene_schema_to_sionna_scene_plan(dto.scene, material_map=material_map)

    return {
        "engine": "sionna_rt",
        "purpose": "internal_precise_validation",
        "scene_plan": scene_plan,
        "antenna": {
            "tx_id": ant.tx_id,
            "position_m": [float(pos[0]), float(pos[1]), float(pos[2])],
            "tx_power_dbm": float(cfg.tx_power_dbm),
            "frequency_ghz": float(cfg.frequency_ghz),
        },
        "solver": {
            "max_depth": int(cfg.reflection_order),
            "measurement_plane_z_m": float(measurement_plane_z_m),
        },
        "material_table": material_map if material_map is not None else DEFAULT_WALL_MATERIAL_TO_SIONNA_ITU,
    }
