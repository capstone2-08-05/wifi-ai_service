"""
Scene graph DTO → RF canonical scene dict (JSON-serializable).

백엔드 API와 분리된 **순수 변환 레이어**만 담당한다.
출력 형식은 `rf_models.Scene.from_dict` 및 `RF_SCENE_HANDOFF_SPEC.md`와 맞춘다.
필드 매핑·TBD: `docs/SCENE_GRAPH_ADAPTER_MAPPING.md`.
서비스는 **2D floorplan** 기준 설명(heatmap·재질·창문·가구)이 전면: `docs/SERVICE_RF_ARCHITECTURE.md`.

**권장 입력:** `backend_scene_dto.SionnaInputDTO` / `SceneSchema` (합의 DTO).

- **Baseline 변환:** `adapter_baseline_dto` (2D 씬 + baseline 규칙, 안테나 z 정책).
- **Sionna 변환:** `adapter_sionna_dto` (3D·ITU 재질·솔버 파라미터 스냅샷).

레거시 dict(JSON)는 `scene_graph_to_rf_scene_dict()` 유지.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Literal, Mapping

from backend_scene_dto import AntennaDTO  # noqa: E402
from backend_scene_dto import SceneSchema as BackendSceneSchema  # noqa: E402
from backend_scene_dto import SimConfigDTO  # noqa: E402
from backend_scene_dto import SionnaInputDTO  # noqa: E402


def _coerce_material_key_for_baseline(material: str) -> str:
    """백엔드 스키마 enum·레거시 프로파일 키는 유지, 그 외는 ``unknown``."""
    from rf_materials import BACKEND_SCHEMA_WALL_MATERIALS, DEFAULT_MATERIAL_PROFILES  # noqa: PLC0415

    s = material.strip()
    if s in DEFAULT_MATERIAL_PROFILES:
        return s
    if s in BACKEND_SCHEMA_WALL_MATERIALS:
        return s
    return "unknown"


def _first_str(d: Mapping[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _require_scene_version_id(graph: Mapping[str, Any]) -> str:
    s = _first_str(graph, "scene_version_id", "sceneVersionId", "version_id")
    if s is None:
        raise ValueError(
            "scene graph must include scene_version_id (or sceneVersionId / version_id)"
        )
    return s


def _normalize_wall(
    raw: Mapping[str, Any],
    *,
    material_id_to_profile_key: dict[str, str] | None,
) -> dict[str, Any]:
    wall_id = _first_str(raw, "id", "wall_id", "wallId")
    if wall_id is None:
        raise ValueError(f"wall entry missing id / wall_id / wallId: {raw!r}")

    role = raw.get("role")
    if role not in ("outer", "inner"):
        raise ValueError(f"wall {wall_id!r}: role must be 'outer' or 'inner', got {role!r}")

    out: dict[str, Any] = {
        "id": wall_id,
        "x1": float(raw["x1"]),
        "y1": float(raw["y1"]),
        "x2": float(raw["x2"]),
        "y2": float(raw["y2"]),
        "thickness": float(raw["thickness"]),
        "height": float(raw["height"]),
        "role": role,
    }

    mat = _resolve_wall_material(
        raw,
        wall_id=wall_id,
        schema_role=role,
        material_id_to_profile_key=material_id_to_profile_key,
    )
    if mat is not None:
        out["material"] = _coerce_material_key_for_baseline(mat)

    vid = _first_str(raw, "version_id", "versionId")
    if vid is not None:
        out["version_id"] = vid

    return out


def _resolve_wall_material(
    raw: Mapping[str, Any],
    *,
    wall_id: str,
    schema_role: str,
    material_id_to_profile_key: dict[str, str] | None,
) -> str | None:
    """RF `material` 문자열 또는 생략(파서 기본값)."""
    direct = raw.get("material")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    mid = raw.get("material_id")
    if mid is None:
        return None
    if not isinstance(mid, str) or not mid.strip():
        return None
    mid = mid.strip()
    if material_id_to_profile_key is None:
        raise ValueError(
            f"wall {wall_id!r} has material_id={mid!r} but material_id_to_profile_key was not provided"
        )
    if mid not in material_id_to_profile_key:
        raise KeyError(
            f"wall {wall_id!r}: unknown material_id {mid!r}; add it to material_id_to_profile_key"
        )
    resolved = material_id_to_profile_key[mid]
    if not isinstance(resolved, str) or not resolved.strip():
        raise ValueError(f"material_id_to_profile_key[{mid!r}] must be a non-empty string")
    return resolved.strip()


def _normalize_opening(
    raw: Mapping[str, Any],
    *,
    scene_version_id: str,
) -> dict[str, Any]:
    o = dict(raw)
    oid = _first_str(o, "id", "opening_id", "openingId")
    if oid is None:
        raise ValueError(f"opening entry missing id: {raw!r}")
    o["id"] = oid

    wid = _first_str(o, "wall_id", "wallId")
    if wid is None:
        raise ValueError(f"opening {oid!r}: missing wall_id / wallId")
    o["wall_id"] = wid

    v_open = _first_str(o, "version_id", "versionId")
    o["version_id"] = v_open if v_open is not None else scene_version_id

    lg = o.get("line_geom")
    if not isinstance(lg, dict) or lg.get("type") != "LineString":
        raise ValueError(f"opening {oid!r}: line_geom must be a GeoJSON LineString object")

    return o


def _normalize_room(raw: Mapping[str, Any], *, scene_version_id: str) -> dict[str, Any]:
    r = dict(raw)
    rid = _first_str(r, "id", "room_id", "roomId")
    if rid is None:
        raise ValueError(f"room entry missing id: {raw!r}")
    r["id"] = rid

    name = _first_str(r, "room_name", "roomName", "name")
    if name is None:
        raise ValueError(f"room {rid!r}: missing room_name / name")
    r["room_name"] = name

    st = _first_str(r, "space_type", "spaceType")
    if st is None:
        raise ValueError(f"room {rid!r}: missing space_type / spaceType")
    r["space_type"] = st

    pg = r.get("polygon_geom")
    if not isinstance(pg, dict) or pg.get("type") != "Polygon":
        raise ValueError(f"room {rid!r}: polygon_geom must be a GeoJSON Polygon object")

    v_room = _first_str(r, "version_id", "versionId")
    r["version_id"] = v_room if v_room is not None else scene_version_id

    return r


def _backend_opening_to_rf(
    opening: Any,
    *,
    scene_version_id: str,
) -> dict[str, Any]:
    """Backend `Opening` (x1..y2, wall_ref) → RF opening dict (line_geom + wall_id)."""
    oid = opening.id.strip() if isinstance(opening.id, str) else str(opening.id)
    wid = opening.wall_ref
    if wid is None or (isinstance(wid, str) and not wid.strip()):
        raise ValueError(f"opening {oid!r}: wall_ref is required for RF wall_id mapping")
    wid = wid.strip()
    width_m = math.hypot(float(opening.x2) - float(opening.x1), float(opening.y2) - float(opening.y1))
    if width_m <= 0:
        raise ValueError(f"opening {oid!r}: degenerate segment (x1,y1)-(x2,y2)")
    otype = opening.type.strip() if isinstance(opening.type, str) else str(opening.type)
    return {
        "id": oid,
        "version_id": scene_version_id,
        "wall_id": wid,
        "opening_type": otype,
        "line_geom": {
            "type": "LineString",
            "coordinates": [
                [float(opening.x1), float(opening.y1)],
                [float(opening.x2), float(opening.y2)],
            ],
        },
        "width_m": max(width_m, 0.01),
    }


def _backend_room_to_rf(room: Any, *, scene_version_id: str) -> dict[str, Any]:
    """Backend `Room` (points, center, area) → RF room dict (polygon_geom, …)."""
    rid = room.id.strip() if isinstance(room.id, str) else str(room.id)
    pts = room.points
    if not isinstance(pts, list) or len(pts) < 3:
        raise ValueError(f"room {rid!r}: points must be a list of at least 3 [x,y] vertices")
    ring: list[list[float]] = []
    for i, p in enumerate(pts):
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            raise TypeError(f"room {rid!r}: points[{i}] must be [x, y]")
        ring.append([float(p[0]), float(p[1])])
    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]

    cen = room.center
    if not isinstance(cen, (list, tuple)) or len(cen) < 2:
        raise ValueError(f"room {rid!r}: center must be [x, y] or longer")
    centroid_geom = {"type": "Point", "coordinates": [float(cen[0]), float(cen[1])]}

    return {
        "id": rid,
        "version_id": scene_version_id,
        "room_name": rid,
        "space_type": "room",
        "polygon_geom": {"type": "Polygon", "coordinates": [ring]},
        "centroid_geom": centroid_geom,
        "area_m2": float(room.area),
    }


def scene_schema_to_rf_scene_dict(
    scene: BackendSceneSchema | Mapping[str, Any],
    *,
    floor_id: str | None = None,
    material_id_to_profile_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    백엔드 ``SceneSchema`` → **Baseline** RF 루트 scene dict.

    (별칭) 내부적으로 ``adapter_baseline_dto.scene_schema_to_baseline_rf_scene_dict`` 와 동일.
    """
    from adapter_baseline_dto import scene_schema_to_baseline_rf_scene_dict  # noqa: PLC0415

    return scene_schema_to_baseline_rf_scene_dict(
        scene,
        floor_id=floor_id,
        material_id_to_profile_key=material_id_to_profile_key,
    )


def antenna_dto_to_ap_layout_dict(
    antenna: AntennaDTO | Mapping[str, Any],
    *,
    scene_version_id: str,
    sim_config: SimConfigDTO | Mapping[str, Any] | None = None,
    layout_name: str = "manual_single",
    layout_type: str = "manual",
) -> dict[str, Any]:
    """
    ``AntennaDTO`` → 단일 AP `ApLayout` JSON (**하위 호환**).

    기존 동작: ``position_m[2]`` 를 ``z_m`` 에 반영. Baseline 전용 옵션은
    ``adapter_baseline_dto.antenna_dto_to_baseline_ap_layout_dict(..., z_policy=...)`` 사용.
    """
    from adapter_baseline_dto import antenna_dto_to_baseline_ap_layout_dict  # noqa: PLC0415

    return antenna_dto_to_baseline_ap_layout_dict(
        antenna,
        scene_version_id=scene_version_id,
        sim_config=sim_config,
        layout_name=layout_name,
        layout_type=layout_type,
        z_policy="use_position_z",
    )


def sionna_input_dto_to_rf_scene_dict(
    payload: SionnaInputDTO | Mapping[str, Any],
    *,
    floor_id: str | None = None,
    material_id_to_profile_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """``SionnaInputDTO`` 전체에서 RF scene 루트 dict만 추출."""
    dto = payload if isinstance(payload, SionnaInputDTO) else SionnaInputDTO.model_validate(payload)
    return scene_schema_to_rf_scene_dict(
        dto.scene,
        floor_id=floor_id,
        material_id_to_profile_key=material_id_to_profile_key,
    )


def sionna_input_dto_to_rf_scene_and_manual_layout(
    payload: SionnaInputDTO | Mapping[str, Any],
    *,
    floor_id: str | None = None,
    material_id_to_profile_key: dict[str, str] | None = None,
    layout_name: str = "manual_single",
    layout_type: str = "manual",
    antenna_z_policy: Literal["ignore", "use_position_z"] = "ignore",
    default_antenna_z_m: float = 2.5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    **Baseline** 한 세트: (RF scene dict, 수동 단일 AP layout).

    기본은 안테나 **z 무시**·``default_antenna_z_m`` (2D preview). ``antenna_z_policy=\"use_position_z`` 로 바꿀 수 있다.
    후보 AP 파이프라인은 동일 scene dict에 ``ap_candidate_generator`` 등을 쓰면 된다.
    """
    from adapter_baseline_dto import sionna_input_dto_to_baseline_scene_and_layout  # noqa: PLC0415

    return sionna_input_dto_to_baseline_scene_and_layout(
        payload,
        floor_id=floor_id,
        material_id_to_profile_key=material_id_to_profile_key,
        layout_name=layout_name,
        layout_type=layout_type,
        antenna_z_policy=antenna_z_policy,
        default_antenna_z_m=default_antenna_z_m,
    )


def sionna_input_dto_to_sionna_engine_plan(
    payload: SionnaInputDTO | Mapping[str, Any],
    *,
    material_map: dict[str, str] | None = None,
    measurement_plane_z_m: float = 1.0,
) -> dict[str, Any]:
    """동일 DTO → Sionna 엔진용 스냅샷 (`adapter_sionna_dto`)."""
    from adapter_sionna_dto import sionna_input_dto_to_engine_plan  # noqa: PLC0415

    return sionna_input_dto_to_engine_plan(
        payload,
        material_map=material_map,
        measurement_plane_z_m=measurement_plane_z_m,
    )


def scene_graph_to_rf_scene_dict(
    graph: Mapping[str, Any],
    *,
    source_type: str | None = None,
    units: str = "m",
    material_id_to_profile_key: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    백엔드 scene graph DTO(dict)를 RF 입력 루트 dict로 변환한다.

    기대 키(일부 별칭 허용):
    - ``scene_version_id`` | ``sceneVersionId`` | ``version_id``
    - ``floor_id`` | ``floorId`` (선택)
    - ``sourceType`` | ``source_type`` (없으면 ``source_type`` 인자 사용)
    - ``walls``: 벽 목록 (``id``/``wall_id``, ``role`` outer|inner, 기하·두께·높이)
    - ``openings``: 개구부 (``line_geom`` LineString, ``wall_id``, …)
    - ``rooms``: 방 (``polygon_geom`` Polygon, ``room_name``/``name``, …)
    - ``objects``: 임의 객체 배열 (기본 ``[]``)

    ``material_id``만 있는 벽은 ``material_id_to_profile_key``로 RF 프로파일 키 문자열로 풀어야 한다.
    """
    scene_version_id = _require_scene_version_id(graph)

    st = _first_str(graph, "sourceType", "source_type")
    if st is None:
        if source_type is None:
            raise ValueError("source_type: pass as argument or set sourceType / source_type on graph")
        st = source_type.strip()
    else:
        st = st.strip()

    if units != "m":
        raise ValueError("units must be 'm' for RF scene input")

    walls_raw = graph.get("walls")
    openings_raw = graph.get("openings")
    rooms_raw = graph.get("rooms")
    if not isinstance(walls_raw, list):
        raise TypeError("graph['walls'] must be a list")
    if not isinstance(openings_raw, list):
        raise TypeError("graph['openings'] must be a list")
    if not isinstance(rooms_raw, list):
        raise TypeError("graph['rooms'] must be a list")

    objects_raw = graph.get("objects")
    if objects_raw is None:
        objects: list[Any] = []
    elif isinstance(objects_raw, list):
        objects = []
        for i, o in enumerate(objects_raw):
            if not isinstance(o, dict):
                raise TypeError(f"objects[{i}] must be a dict")
            objects.append(copy.deepcopy(o))
    else:
        raise TypeError("graph['objects'] must be a list when present")

    walls: list[dict[str, Any]] = []
    for i, w in enumerate(walls_raw):
        if not isinstance(w, dict):
            raise TypeError(f"walls[{i}] must be a dict")
        walls.append(_normalize_wall(w, material_id_to_profile_key=material_id_to_profile_key))

    openings: list[dict[str, Any]] = []
    for i, o in enumerate(openings_raw):
        if not isinstance(o, dict):
            raise TypeError(f"openings[{i}] must be a dict")
        openings.append(_normalize_opening(o, scene_version_id=scene_version_id))

    rooms: list[dict[str, Any]] = []
    for i, r in enumerate(rooms_raw):
        if not isinstance(r, dict):
            raise TypeError(f"rooms[{i}] must be a dict")
        rooms.append(_normalize_room(r, scene_version_id=scene_version_id))

    floor_id = _first_str(graph, "floor_id", "floorId")

    out: dict[str, Any] = {
        "units": units,
        "sourceType": st,
        "scene_version_id": scene_version_id,
        "walls": walls,
        "openings": openings,
        "rooms": rooms,
        "objects": objects,
    }
    if floor_id is not None:
        out["floor_id"] = floor_id
    return out
