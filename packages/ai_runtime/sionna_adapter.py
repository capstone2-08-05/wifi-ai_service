"""Sionna engine plan adapter.

도메인 객체(FloorScene, AccessPoint, RadioMaterial, SimulationConfig,
MeasurementPlane)를 받아 Sionna RT runtime이 소비할 engine plan(dict)으로
변환한다.

이 모듈의 책임은 domain → Sionna 표현 변환뿐이다.
- domain 단계에서 의미 분리/검증은 끝났다고 가정한다.
- material id → Sionna ITU material key 매핑은 `RadioMaterial.sionna_material_key`로
  도메인에 내재화되어 있으므로 adapter는 dict 룩업/normalize를 하지 않는다.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.domain.entities.geometry import FloorScene, SceneBounds
from app.domain.entities.radio import (
    AccessPoint,
    MeasurementPlane,
    RadioMaterial,
    SimulationConfig,
    radio_material_table,
)


def _resolve_material(
    material_id: str, table: Mapping[str, RadioMaterial]
) -> RadioMaterial:
    if material_id not in table:
        raise ValueError(f"unknown material_id: {material_id}")
    return table[material_id]


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
                "sionna_material_key": material.sionna_material_key,
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
            "sionna_material_key": _resolve_material(opening.material_id, table).sionna_material_key,
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
            "sionna_material_key": _resolve_material(piece.material_id, table).sionna_material_key,
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
    simulation: SimulationConfig,
    measurement_plane: MeasurementPlane,
    materials: Mapping[str, RadioMaterial] | None = None,
) -> dict[str, Any]:
    """도메인 객체 묶음을 Sionna runtime용 plan으로 변환."""
    table = dict(materials) if materials is not None else radio_material_table()

    bounds = measurement_plane.bounds or scene.bounds or scene.compute_bounds()
    if not bounds.contains_xy(access_point.x, access_point.y):
        raise ValueError(
            f"AP {access_point.id} position ({access_point.x}, {access_point.y}) "
            "is outside scene bounds"
        )

    freq_ghz = access_point.frequency_ghz or simulation.physical.frequency_ghz
    tx_power_dbm = (
        access_point.tx_power_dbm
        if access_point.tx_power_dbm is not None
        else simulation.physical.tx_power_dbm
    )

    return {
        "engine": "sionna_rt",
        "scene_plan": _scene_to_plan(scene, table),
        "antenna": {
            "tx_id": access_point.id,
            "position_m": [float(access_point.x), float(access_point.y), float(access_point.z)],
            "frequency_ghz": float(freq_ghz),
            "tx_power_dbm": float(tx_power_dbm),
        },
        "measurement_plane": {
            "z_m": float(measurement_plane.z_m),
            "cell_size_m": float(measurement_plane.cell_size_m),
            "bounds": _bounds_to_dict(bounds),
        },
        "config": {
            "physical": simulation.physical.model_dump(),
            "propagation": simulation.propagation.model_dump(),
            "solver": simulation.solver.model_dump(),
        },
    }
