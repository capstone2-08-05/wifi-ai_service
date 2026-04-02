from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


class SchemaValidationError(ValueError):
    """Raised when the RF input JSON does not satisfy the expected schema."""


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    @classmethod
    def from_sequence(cls, values: Sequence[float]) -> "Point2D":
        if len(values) != 2:
            raise SchemaValidationError(f"Point must have 2 values, got {values!r}")
        return cls(x=float(values[0]), y=float(values[1]))

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class Wall:
    wall_id: str
    version_id: str
    wall_role: str
    start: Point2D
    end: Point2D
    thickness_m: float
    height_m: float
    material: str

    @property
    def is_exterior(self) -> bool:
        return self.wall_role == "exterior"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Wall":
        coords = _read_linestring_coordinates(data, field_name="centerline_geom")
        return cls(
            wall_id=_require_str(data, "id"),
            version_id=_require_str(data, "version_id"),
            wall_role=str(data.get("wall_role", "interior")),
            start=Point2D.from_sequence(coords[0]),
            end=Point2D.from_sequence(coords[1]),
            thickness_m=_require_positive_number(data, "thickness_m"),
            height_m=_require_positive_number(data, "height_m"),
            material=_require_str(data, "material"),
        )


@dataclass(frozen=True)
class Opening:
    opening_id: str
    version_id: str
    wall_id: str
    opening_type: str
    start: Point2D
    end: Point2D
    width_m: float
    sill_height_m: float | None
    head_height_m: float | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Opening":
        coords = _read_linestring_coordinates(data, field_name="line_geom")
        sill = _optional_number(data, "sill_height_m")
        head = _optional_number(data, "head_height_m")
        if sill is not None and head is not None and head <= sill:
            raise SchemaValidationError(
                f"opening {data.get('id')} must satisfy head_height_m > sill_height_m"
            )
        return cls(
            opening_id=_require_str(data, "id"),
            version_id=_require_str(data, "version_id"),
            wall_id=_require_str(data, "wall_id"),
            opening_type=_require_str(data, "opening_type"),
            start=Point2D.from_sequence(coords[0]),
            end=Point2D.from_sequence(coords[1]),
            width_m=_require_positive_number(data, "width_m"),
            sill_height_m=sill,
            head_height_m=head,
        )


@dataclass(frozen=True)
class Room:
    room_id: str
    version_id: str
    room_name: str
    space_type: str
    polygon: tuple[Point2D, ...]
    centroid: Point2D | None
    area_m2: float | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Room":
        polygon = tuple(
            Point2D.from_sequence(coord)
            for coord in _read_polygon_coordinates(data, field_name="polygon_geom")
        )
        centroid = None
        centroid_geom = data.get("centroid_geom")
        if centroid_geom is not None:
            coords = centroid_geom.get("coordinates")
            centroid = Point2D.from_sequence(coords)
        return cls(
            room_id=_require_str(data, "id"),
            version_id=_require_str(data, "version_id"),
            room_name=_require_str(data, "room_name"),
            space_type=_require_str(data, "space_type"),
            polygon=polygon,
            centroid=centroid,
            area_m2=_optional_number(data, "area_m2"),
        )


@dataclass(frozen=True)
class Scene:
    scene_version_id: str
    coordinate_unit: str
    floor_id: str | None
    walls: tuple[Wall, ...]
    openings: tuple[Opening, ...]
    rooms: tuple[Room, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        coordinate_unit = _require_str(data, "coordinate_unit")
        if coordinate_unit != "meter":
            raise SchemaValidationError(
                f"coordinate_unit must be 'meter', got {coordinate_unit!r}"
            )

        scene_version_id = _require_str(data, "scene_version_id")
        walls = tuple(Wall.from_dict(item) for item in _require_list(data, "walls"))
        openings = tuple(Opening.from_dict(item) for item in _require_list(data, "openings"))
        rooms = tuple(Room.from_dict(item) for item in _require_list(data, "rooms"))

        wall_ids = {wall.wall_id for wall in walls}
        for opening in openings:
            if opening.wall_id not in wall_ids:
                raise SchemaValidationError(
                    f"opening {opening.opening_id} references unknown wall_id {opening.wall_id!r}"
                )

        return cls(
            scene_version_id=scene_version_id,
            coordinate_unit=coordinate_unit,
            floor_id=data.get("floor_id"),
            walls=walls,
            openings=openings,
            rooms=rooms,
        )

    def bounds(self) -> tuple[float, float, float, float]:
        points: list[Point2D] = []
        for wall in self.walls:
            points.extend([wall.start, wall.end])
        for room in self.rooms:
            points.extend(room.polygon)
        if not points:
            raise SchemaValidationError("Scene has no geometry to infer bounds")
        min_x = min(point.x for point in points)
        max_x = max(point.x for point in points)
        min_y = min(point.y for point in points)
        max_y = max(point.y for point in points)
        return min_x, max_x, min_y, max_y


@dataclass(frozen=True)
class AccessPoint:
    ap_id: str
    ap_name: str
    position: Point2D
    z_m: float
    tx_power_dbm: float
    frequency_ghz: float
    azimuth_deg: float
    tilt_deg: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccessPoint":
        point = data.get("point_geom")
        if point is None or point.get("type") != "Point":
            raise SchemaValidationError("AP must define point_geom with GeoJSON Point")
        return cls(
            ap_id=_require_str(data, "id"),
            ap_name=_require_str(data, "ap_name"),
            position=Point2D.from_sequence(point.get("coordinates")),
            z_m=_require_number(data, "z_m"),
            tx_power_dbm=_require_number(data, "tx_power_dbm"),
            frequency_ghz=_require_positive_number(data, "frequency_ghz"),
            azimuth_deg=float(data.get("azimuth_deg", 0.0)),
            tilt_deg=float(data.get("tilt_deg", 0.0)),
        )


@dataclass(frozen=True)
class ApLayout:
    scene_version_id: str
    layout_name: str
    layout_type: str
    aps: tuple[AccessPoint, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApLayout":
        aps = tuple(AccessPoint.from_dict(item) for item in _require_list(data, "aps"))
        if not aps:
            raise SchemaValidationError("ApLayout must contain at least one AP")
        return cls(
            scene_version_id=_require_str(data, "scene_version_id"),
            layout_name=_require_str(data, "layout_name"),
            layout_type=_require_str(data, "layout_type"),
            aps=aps,
        )


@dataclass(frozen=True)
class SimulationConfig:
    scene_version_id: str
    grid_resolution_m: float
    path_loss_constant_db: float
    path_loss_exponent: float
    include_exterior_walls: bool
    output_dir_name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SimulationConfig":
        return cls(
            scene_version_id=_require_str(data, "scene_version_id"),
            grid_resolution_m=_require_positive_number(data, "grid_resolution_m"),
            path_loss_constant_db=float(data.get("path_loss_constant_db", 40.0)),
            path_loss_exponent=float(data.get("path_loss_exponent", 2.0)),
            include_exterior_walls=bool(data.get("include_exterior_walls", False)),
            output_dir_name=str(data.get("output_dir_name", "output")),
        )


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError(f"{key} must be a non-empty string")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise SchemaValidationError(f"{key} must be a list")
    return value


def _require_number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{key} must be a number")
    return float(value)


def _optional_number(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{key} must be a number when provided")
    return float(value)


def _require_positive_number(data: dict[str, Any], key: str) -> float:
    value = _require_number(data, key)
    if value <= 0:
        raise SchemaValidationError(f"{key} must be > 0")
    return value


def _read_linestring_coordinates(data: dict[str, Any], field_name: str) -> list[list[float]]:
    geom = data.get(field_name)
    if not isinstance(geom, dict) or geom.get("type") != "LineString":
        raise SchemaValidationError(f"{field_name} must be a GeoJSON LineString")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) != 2:
        raise SchemaValidationError(f"{field_name}.coordinates must contain exactly 2 points")
    return coords


def _read_polygon_coordinates(data: dict[str, Any], field_name: str) -> list[list[float]]:
    geom = data.get(field_name)
    if not isinstance(geom, dict) or geom.get("type") != "Polygon":
        raise SchemaValidationError(f"{field_name} must be a GeoJSON Polygon")
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or not coords or not isinstance(coords[0], list):
        raise SchemaValidationError(f"{field_name}.coordinates must contain polygon rings")
    outer_ring = coords[0]
    if len(outer_ring) < 4:
        raise SchemaValidationError(f"{field_name} outer ring must contain at least 4 points")
    return outer_ring
