from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence


class SchemaValidationError(ValueError):
    """Raised when the RF input JSON does not satisfy the expected schema."""


def _wall_material_from_payload(data: dict[str, Any], *, schema_role: str) -> str:
    """SceneSchema has no material; RF defaults by role, optional non-empty override."""
    override = data.get("material")
    if override is not None:
        if not isinstance(override, str) or not override.strip():
            raise SchemaValidationError("material must be a non-empty string when provided")
        return override.strip()
    return "concrete" if schema_role == "outer" else "unknown"


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
    def from_dict(cls, data: dict[str, Any], *, scene_version_id: str) -> "Wall":
        """Parse a wall item from SceneSchema (endpoints + role) or optional RF extensions."""
        wall_id = _require_str(data, "id")
        version_id = data.get("version_id")
        if version_id is not None and isinstance(version_id, str) and version_id.strip():
            vid = version_id.strip()
        else:
            vid = scene_version_id

        role = data.get("role")
        if isinstance(role, str) and role in ("outer", "inner"):
            x1 = _require_number(data, "x1")
            y1 = _require_number(data, "y1")
            x2 = _require_number(data, "x2")
            y2 = _require_number(data, "y2")
            thickness_m = _require_positive_number(data, "thickness")
            height_m = _require_positive_number(data, "height")
            wall_role = "exterior" if role == "outer" else "interior"
            material = _wall_material_from_payload(data, schema_role=role)
            return cls(
                wall_id=wall_id,
                version_id=vid,
                wall_role=wall_role,
                start=Point2D(x=x1, y=y1),
                end=Point2D(x=x2, y=y2),
                thickness_m=thickness_m,
                height_m=height_m,
                material=material,
            )

        raise SchemaValidationError(
            "wall must define SceneSchema fields id, x1, y1, x2, y2, thickness, height, "
            "and role (outer|inner)"
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
    """In-memory scene aligned to backend SceneSchema root + RF extensions."""

    units: str
    source_type: str
    scene_version_id: str
    floor_id: str | None
    objects: tuple[dict[str, Any], ...]
    walls: tuple[Wall, ...]
    openings: tuple[Opening, ...]
    rooms: tuple[Room, ...]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        units = _require_str(data, "units")
        if units != "m":
            raise SchemaValidationError(f"units must be 'm', got {units!r}")

        source_type = _require_str(data, "sourceType")
        _require_list(data, "walls")
        _require_list(data, "openings")
        _require_list(data, "rooms")
        objects_raw = _require_list(data, "objects")
        for i, obj in enumerate(objects_raw):
            if not isinstance(obj, dict):
                raise SchemaValidationError(f"objects[{i}] must be an object")

        scene_version_id = data.get("scene_version_id")
        if isinstance(scene_version_id, str) and scene_version_id.strip():
            svid = scene_version_id.strip()
        else:
            svid = source_type

        wall_items = _require_list(data, "walls")
        for i, item in enumerate(wall_items):
            if not isinstance(item, dict):
                raise SchemaValidationError(f"walls[{i}] must be an object")
        walls = tuple(Wall.from_dict(item, scene_version_id=svid) for item in wall_items)

        opening_items = _require_list(data, "openings")
        for i, item in enumerate(opening_items):
            if not isinstance(item, dict):
                raise SchemaValidationError(f"openings[{i}] must be an object")
        openings = tuple(Opening.from_dict(item) for item in opening_items)

        room_items = _require_list(data, "rooms")
        for i, item in enumerate(room_items):
            if not isinstance(item, dict):
                raise SchemaValidationError(f"rooms[{i}] must be an object")
        rooms = tuple(Room.from_dict(item) for item in room_items)

        wall_ids = {wall.wall_id for wall in walls}
        for opening in openings:
            if opening.wall_id not in wall_ids:
                raise SchemaValidationError(
                    f"opening {opening.opening_id} references unknown wall_id {opening.wall_id!r}"
                )

        raw_floor = data.get("floor_id")
        if raw_floor is None:
            floor_id = None
        elif isinstance(raw_floor, str) and raw_floor.strip():
            floor_id = raw_floor.strip()
        else:
            floor_id = None

        return cls(
            units=units,
            source_type=source_type,
            scene_version_id=svid,
            floor_id=floor_id,
            objects=tuple(dict(obj) for obj in objects_raw),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.ap_id,
            "ap_name": self.ap_name,
            "point_geom": {
                "type": "Point",
                "coordinates": [self.position.x, self.position.y],
            },
            "z_m": self.z_m,
            "tx_power_dbm": self.tx_power_dbm,
            "frequency_ghz": self.frequency_ghz,
            "azimuth_deg": self.azimuth_deg,
            "tilt_deg": self.tilt_deg,
        }

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_version_id": self.scene_version_id,
            "layout_name": self.layout_name,
            "layout_type": self.layout_type,
            "aps": [ap.to_dict() for ap in self.aps],
        }

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
    first = outer_ring[0]
    last = outer_ring[-1]
    if first != last:
        raise SchemaValidationError(
            f"{field_name} outer ring must be closed (first coordinate must equal last)"
        )
    return outer_ring
