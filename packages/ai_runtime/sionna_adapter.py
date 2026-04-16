"""Sionna engine plan adapter from backend DTO payload."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, Field

from packages.contracts.floorplan import SceneSchema

BACKEND_SCHEMA_WALL_MATERIALS = frozenset(("concrete", "glass", "wood", "metal", "unknown"))
WALL_TO_SIONNA_ITU: dict[str, str] = {
    "concrete": "concrete",
    "glass": "glass",
    "wood": "wood",
    "metal": "metal",
    "unknown": "plasterboard",
}
LEGACY_EXTRA_TO_SIONNA_ITU: dict[str, str] = {
    "brick": "brick",
    "marble": "marble",
    "chipboard": "chipboard",
    "floorboard": "floorboard",
    "ceiling_board": "ceiling_board",
}
DEFAULT_WALL_MATERIAL_TO_SIONNA_ITU: dict[str, str] = {
    **WALL_TO_SIONNA_ITU,
    **LEGACY_EXTRA_TO_SIONNA_ITU,
    "drywall": "plasterboard",
}


class SimConfigDTO(BaseModel):
    frequency_ghz: float = 28.0
    tx_power_dbm: float = 30.0
    reflection_order: int = 2
    measurement_plane_z_m: float = 1.0


class AntennaDTO(BaseModel):
    tx_id: str = "router_1"
    position_m: list[float] = Field(..., description="[x, y, z] in meters")


class SionnaInputDTO(BaseModel):
    config: SimConfigDTO
    antenna: AntennaDTO
    scene: SceneSchema


def normalize_wall_material_key(raw: str) -> str:
    if not isinstance(raw, str):
        return "unknown"
    s = raw.strip().lower()
    if not s:
        return "unknown"
    if s in ("drywall", "gypsum", "plasterboard"):
        return "wood"
    if s in BACKEND_SCHEMA_WALL_MATERIALS:
        return s
    return "unknown"


def map_wall_material_to_sionna_itur(
    wall_material_key: str,
    *,
    table: dict[str, str] | None = None,
) -> str:
    merged_extra = {**LEGACY_EXTRA_TO_SIONNA_ITU, **(table or {})}
    key = wall_material_key.strip() if isinstance(wall_material_key, str) else str(wall_material_key)
    lowered = key.lower()
    if lowered in merged_extra:
        return merged_extra[lowered]
    normalized = normalize_wall_material_key(key)
    return WALL_TO_SIONNA_ITU.get(normalized, "plasterboard")


def _scene_schema_to_sionna_scene_plan(
    scene: SceneSchema | Mapping[str, Any],
    *,
    material_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(scene, SceneSchema):
        scene = SceneSchema.model_validate(scene)

    walls: list[dict[str, Any]] = []
    for wall in scene.walls:
        walls.append(
            {
                "id": wall.id,
                "x1": float(wall.x1),
                "y1": float(wall.y1),
                "x2": float(wall.x2),
                "y2": float(wall.y2),
                "thickness_m": float(wall.thickness),
                "height_m": float(wall.height),
                "role": wall.role,
                "wall_material": wall.material,
                "itu_radio_material": map_wall_material_to_sionna_itur(wall.material, table=material_map),
            }
        )

    openings = [
        {
            "id": opening.id,
            "type": opening.type,
            "x1": float(opening.x1),
            "y1": float(opening.y1),
            "x2": float(opening.x2),
            "y2": float(opening.y2),
            "wall_ref": opening.wall_ref,
        }
        for opening in scene.openings
    ]
    rooms = [
        {
            "id": room.id,
            "points": room.points,
            "center": room.center,
            "area_m2": float(room.area),
        }
        for room in scene.rooms
    ]

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
) -> dict[str, Any]:
    dto = payload if isinstance(payload, SionnaInputDTO) else SionnaInputDTO.model_validate(payload)
    cfg = dto.config
    ant = dto.antenna
    pos = ant.position_m
    if not isinstance(pos, (list, tuple)) or len(pos) < 3:
        raise ValueError("Sionna path requires antenna.position_m [x, y, z]")

    return {
        "engine": "sionna_rt",
        "purpose": "internal_precise_validation",
        "scene_plan": _scene_schema_to_sionna_scene_plan(dto.scene, material_map=material_map),
        "antenna": {
            "tx_id": ant.tx_id,
            "position_m": [float(pos[0]), float(pos[1]), float(pos[2])],
            "tx_power_dbm": float(cfg.tx_power_dbm),
            "frequency_ghz": float(cfg.frequency_ghz),
        },
        "solver": {
            "max_depth": int(cfg.reflection_order),
            "measurement_plane_z_m": float(cfg.measurement_plane_z_m),
        },
        "material_table": material_map if material_map is not None else DEFAULT_WALL_MATERIAL_TO_SIONNA_ITU,
    }
