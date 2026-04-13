"""
Scene graph DTO → RF canonical scene dict (JSON-serializable).

백엔드 API와 분리된 **순수 변환 레이어**만 담당한다.
출력 형식은 `rf_models.Scene.from_dict` 및 `RF_SCENE_HANDOFF_SPEC.md`와 맞춘다.
필드 매핑·TBD: `docs/SCENE_GRAPH_ADAPTER_MAPPING.md`.
서비스는 **2D floorplan** 기준 설명(heatmap·재질·창문·가구)이 전면: `docs/SERVICE_RF_ARCHITECTURE.md`.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping


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
        out["material"] = mat

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
