"""Sionna engine plan adapter.

도메인 객체(FloorScene, AccessPoint, RadioMaterial, SimulationConfig,
MeasurementPlane)를 받아 Sionna RT runtime이 소비할 engine plan(dict)으로
변환한다.

이 모듈의 책임은 domain → Sionna 표현 변환뿐이다.
- domain 단계에서 의미 분리/검증은 끝났다고 가정한다.
- material id → Sionna ITU material key 매핑은 `RadioMaterial.sionna_material_key`로
  도메인에 내재화되어 있으므로 adapter는 dict 룩업/normalize를 하지 않는다.

주의 — 현재 적용 범위:
- **Wall**: opening 위치에서 segment 단위로 분할되어 Sionna `SceneObject` 로 mesh 생성.
  같은 wall에 여러 opening이 있으면 그 사이마다 segment가 만들어진다.
- **Opening (door/window)**: wall 축에 정렬된 박스로 mesh 생성. `bottom_z_m` / `height_m` 으로
  창문(sill 위)과 닫힌 문(바닥부터)을 구분. material 은 opening 자체의 `material_id` 사용
  (보통 door=wood, window=glass). 열린 문 시나리오는 후속 (`is_open: bool` 필드 추가 시).
- **Furniture**: `polygon_xy` 를 z 축으로 `height_m` 만큼 extrusion 한 prism mesh 생성.
  ITURadioMaterial thickness 우선순위: piece.radio_thickness_m > scene_defaults.furniture_default_thickness_m > 0.1m 모듈 fallback.
- RadioMaterial calibration 필드:
    - `attenuation_scale` — **적용됨**. runtime이 ITURadioMaterial thickness 에 곱하여
      transmission/reflection loss 를 조정. 기하학적 mesh는 영향받지 않는다.
    - `loss_offset_db` — **deferred**. per-cell material mask 인프라 도입 시 적용 예정.
    - `learnable` — metadata flag. differentiable optimization 진입점이 생기면 사용.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.domain.entities.geometry import FloorScene, SceneBounds
from app.domain.entities.radio import (
    AccessPoint,
    MeasurementPlane,
    RadioMaterial,
    ResolvedSionnaConfig,
)


def _resolve_material(
    material_id: str, table: Mapping[str, RadioMaterial]
) -> RadioMaterial:
    if material_id not in table:
        raise ValueError(f"unknown material_id: {material_id}")
    return table[material_id]


def _material_payload(material: RadioMaterial) -> dict[str, Any]:
    """material_id 참조 대상이 plan에 갖는 공통 필드.

    `sionna_material_key`: runtime이 ITURadioMaterial 생성 시 사용.
    `attenuation_scale`: runtime이 ITU material thickness 곱셈에 사용 (applied).
    `loss_offset_db`: per-cell mask 인프라(Issue 2.2)가 들어오면 사용 (현재 deferred).
    `learnable`: differentiable optimization 진입점이 생기면 사용 (현재 metadata).
    """
    return {
        "sionna_material_key": material.sionna_material_key,
        "attenuation_scale": float(material.attenuation_scale),
        "loss_offset_db": float(material.loss_offset_db),
        "learnable": bool(material.learnable),
    }


def _scene_to_plan(scene: FloorScene, table: Mapping[str, RadioMaterial]) -> dict[str, Any]:
    walls: list[dict[str, Any]] = []
    for wall in scene.walls:
        material = _resolve_material(wall.material_id, table)
        walls.append(
            {
                "id": wall.id,
                "x1": float(wall.start_xy[0]),
                "y1": float(wall.start_xy[1]),
                "x2": float(wall.end_xy[0]),
                "y2": float(wall.end_xy[1]),
                "thickness_m": float(wall.thickness_m),
                "height_m": float(wall.height_m),
                "material_id": wall.material_id,
                **_material_payload(material),
            }
        )

    openings = [
        {
            "id": opening.id,
            "wall_id": opening.wall_id,
            "kind": str(opening.kind),
            "center_xy": [float(opening.center_xy[0]), float(opening.center_xy[1])],
            "width_m": float(opening.width_m),
            "bottom_z_m": float(opening.bottom_z_m),
            "height_m": float(opening.height_m),
            "material_id": opening.material_id,
            **_material_payload(_resolve_material(opening.material_id, table)),
        }
        for opening in scene.openings
    ]
    rooms = [
        {"id": room.id, "polygon_xy": [[float(x), float(y)] for x, y in room.polygon_xy]}
        for room in scene.rooms
    ]
    furniture = [
        {
            "id": piece.id,
            "polygon_xy": [[float(x), float(y)] for x, y in piece.polygon_xy],
            "height_m": float(piece.height_m),
            "material_id": piece.material_id,
            # None 이면 runtime 이 scene_defaults.furniture_default_thickness_m 로 fallback
            "radio_thickness_m": (
                float(piece.radio_thickness_m)
                if piece.radio_thickness_m is not None
                else None
            ),
            **_material_payload(_resolve_material(piece.material_id, table)),
        }
        for piece in scene.furniture
    ]

    return {
        "scene_id": scene.scene_id,
        "walls": walls,
        "openings": openings,
        "rooms": rooms,
        "furniture": furniture,
    }


def _bounds_to_dict(b: SceneBounds) -> dict[str, float]:
    return {"min_x": b.min_x, "max_x": b.max_x, "min_y": b.min_y, "max_y": b.max_y}


def build_engine_plan(
    *,
    scene: FloorScene,
    access_point: AccessPoint,
    resolved_config: ResolvedSionnaConfig,
    measurement_plane: MeasurementPlane,
) -> dict[str, Any]:
    """도메인 + 이미 resolve된 config 를 Sionna runtime용 plan dict 으로 변환.

    materials 는 `resolved_config.materials` 가 단일 진실 — 이 시점에서는 이미 request /
    correction_profile / app_defaults 가 merge 끝난 상태.
    """
    table = dict(resolved_config.materials)

    bounds = measurement_plane.bounds or scene.bounds or scene.compute_bounds()
    if not bounds.contains_xy(access_point.x, access_point.y):
        raise ValueError(
            f"AP {access_point.id} position ({access_point.x}, {access_point.y}) "
            "is outside scene bounds"
        )

    physical = resolved_config.physical
    freq_ghz = access_point.frequency_ghz or physical.frequency_ghz
    base_tx_power = (
        access_point.tx_power_dbm
        if access_point.tx_power_dbm is not None
        else physical.tx_power_dbm
    )
    # 전역 보정 — runtime이 적용하기 전에 plan 에서 미리 더한 값을 전달.
    tx_power_dbm = float(base_tx_power) + float(physical.tx_power_offset_db)

    return {
        "engine": "sionna_rt",
        "scene_plan": _scene_to_plan(scene, table),
        "antenna": {
            "tx_id": access_point.id,
            "position_m": [float(access_point.x), float(access_point.y), float(access_point.z)],
            "frequency_ghz": float(freq_ghz),
            "tx_power_dbm": tx_power_dbm,
        },
        "measurement_plane": {
            "z_m": float(measurement_plane.z_m),
            "cell_size_m": float(measurement_plane.cell_size_m),
            "bounds": _bounds_to_dict(bounds),
        },
        "config": {
            "physical": physical.model_dump(),
            "propagation": resolved_config.propagation.model_dump(),
            "solver": resolved_config.solver.model_dump(),
            "scene_defaults": resolved_config.scene_defaults.model_dump(),
            "antenna": resolved_config.antenna.model_dump(),
            "visualization": resolved_config.visualization.model_dump(),
            "provenance": dict(resolved_config.provenance),
        },
    }
