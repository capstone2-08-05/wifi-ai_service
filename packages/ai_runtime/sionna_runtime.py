from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

logger = logging.getLogger(__name__)

INVALID_DBM_THRESHOLD = -200.0

# Material thickness key를 (sionna_material_key, effective_thickness) 로 캐시할 때
# float precision 흔들림을 막기 위해 반올림하는 자릿수.
_MATERIAL_CACHE_PRECISION = 6

# Wall segment / opening 분할 시 길이가 이보다 작은 조각은 무시.
_SEGMENT_MIN_LENGTH_M = 1e-3

# Furniture 의 ITURadioMaterial thickness 기본값 (m). 가구는 wall처럼 명시적 thickness가 없어서
# 대표값을 쓴다. attenuation_scale 로 보정 가능.
_FURNITURE_DEFAULT_THICKNESS_M = 0.1


def _to_numpy(x: Any) -> np.ndarray:
    if hasattr(x, "numpy"):
        return np.asarray(x.numpy())
    return np.asarray(x)


def _rss_w_to_dbm(rss_w: np.ndarray) -> np.ndarray:
    safe = np.maximum(rss_w, 1e-30)
    return 10.0 * np.log10(safe * 1e3)


def _coverage_summary(dbm_map: np.ndarray, valid_mask: np.ndarray) -> dict[str, float | int]:
    flat = dbm_map.reshape(-1)
    flat_valid = valid_mask.reshape(-1)
    valid_values = flat[flat_valid]
    total_count = int(flat.size)
    valid_count = int(valid_values.size)
    if valid_count == 0:
        return {
            "ge_-67": 0.0,
            "ge_-70": 0.0,
            "ge_-75": 0.0,
            "valid_cell_count": 0,
            "total_cell_count": total_count,
            "valid_cell_ratio": 0.0,
        }
    return {
        "ge_-67": float(np.mean(valid_values >= -67.0)),
        "ge_-70": float(np.mean(valid_values >= -70.0)),
        "ge_-75": float(np.mean(valid_values >= -75.0)),
        "valid_cell_count": valid_count,
        "total_cell_count": total_count,
        "valid_cell_ratio": float(valid_count / max(total_count, 1)),
    }


def _nearest_valid_cell(
    dbm_map: np.ndarray,
    valid_mask: np.ndarray,
    cy: int,
    cx: int,
) -> tuple[float | None, bool, str]:
    if valid_mask[cy, cx]:
        return float(dbm_map[cy, cx]), True, "center"

    ys, xs = np.where(valid_mask)
    if ys.size == 0:
        return None, False, "none"

    dy = ys.astype(float) - float(cy)
    dx = xs.astype(float) - float(cx)
    idx = int(np.argmin(dx * dx + dy * dy))
    return float(dbm_map[int(ys[idx]), int(xs[idx])]), False, "nearest_valid"


def _write_floor_obj(path: Path, *, min_x: float, max_x: float, min_y: float, max_y: float) -> None:
    lines = [
        f"v {min_x:.6f} {min_y:.6f} 0.0",
        f"v {max_x:.6f} {min_y:.6f} 0.0",
        f"v {max_x:.6f} {max_y:.6f} 0.0",
        f"v {min_x:.6f} {max_y:.6f} 0.0",
        "f 1 2 3",
        "f 1 3 4",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_wall_box_obj(
    path: Path,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    thickness: float,
    height: float,
    bottom_z: float = 0.0,
) -> None:
    """벽/도어/창문 같이 두 점 사이의 직사각형 면을 두께로 늘린 box.

    `bottom_z` 가 0이 아니면 (예: 창문) 박스가 바닥에서 떠 있다.
    """
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return
    nx = -dy / length
    ny = dx / length
    hx = nx * (thickness / 2.0)
    hy = ny * (thickness / 2.0)
    top_z = bottom_z + height

    a = (x1 + hx, y1 + hy, bottom_z)
    b = (x2 + hx, y2 + hy, bottom_z)
    c = (x2 - hx, y2 - hy, bottom_z)
    d = (x1 - hx, y1 - hy, bottom_z)
    e = (a[0], a[1], top_z)
    f = (b[0], b[1], top_z)
    g = (c[0], c[1], top_z)
    h = (d[0], d[1], top_z)

    verts = [a, b, c, d, e, f, g, h]
    lines = [f"v {vx:.6f} {vy:.6f} {vz:.6f}" for vx, vy, vz in verts]
    lines += [
        "f 1 2 3",
        "f 1 3 4",
        "f 5 7 6",
        "f 5 8 7",
        "f 1 5 6",
        "f 1 6 2",
        "f 2 6 7",
        "f 2 7 3",
        "f 3 7 8",
        "f 3 8 4",
        "f 4 8 5",
        "f 4 5 1",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_extruded_polygon_obj(
    path: Path,
    *,
    polygon_xy: list[tuple[float, float]] | list[list[float]],
    height: float,
    bottom_z: float = 0.0,
) -> None:
    """polygon 을 z 축으로 height 만큼 extrude한 prism mesh를 OBJ로 저장.

    가구(box-like) 표현에 사용. self-intersecting polygon은 검증하지 않으므로
    호출자가 보장해야 한다 (FurnitureObject는 단순 검증만 한다).

    삼각화는 fan triangulation (convex 가정).
    """
    pts = [(float(p[0]), float(p[1])) for p in polygon_xy if len(p) >= 2]
    n = len(pts)
    if n < 3:
        return
    top_z = bottom_z + height

    verts: list[tuple[float, float, float]] = []
    for x, y in pts:
        verts.append((x, y, bottom_z))
    for x, y in pts:
        verts.append((x, y, top_z))

    lines = [f"v {vx:.6f} {vy:.6f} {vz:.6f}" for vx, vy, vz in verts]
    # bottom face — fan triangulation around vertex 1 (CCW seen from below = CW seen from above)
    for i in range(1, n - 1):
        lines.append(f"f 1 {i + 2} {i + 1}")
    # top face — fan around vertex (n+1)
    for i in range(1, n - 1):
        lines.append(f"f {n + 1} {n + 1 + i} {n + 2 + i}")
    # side quads (two triangles each)
    for i in range(n):
        b0 = i + 1
        b1 = (i + 1) % n + 1
        t0 = b0 + n
        t1 = b1 + n
        lines.append(f"f {b0} {b1} {t1}")
        lines.append(f"f {b0} {t1} {t0}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_sionna_rt_from_engine_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Engine plan을 받아 Sionna RT RadioMapSolver를 실행한다.

    plan은 ai_api `app.infrastructure.ai_runtime.sionna_adapter.build_engine_plan` 또는
    sagemaker `apps.sagemaker_rf_inference.app.runtime._build_engine_plan`이 생성하는 구조와
    동일한 키를 가져야 한다 — 즉 solver/propagation/physical 설정이 plan 안에
    이미 포함되어 있다. 더 이상 함수 kwargs로 solver 옵션을 받지 않는다.
    """
    try:
        from sionna.rt import ITURadioMaterial, PlanarArray, RadioMapSolver, SceneObject, Transmitter, load_scene
    except Exception as exc:
        raise ImportError(
            "Sionna runtime is not available. Install runtime dependencies for sionna.rt."
        ) from exc

    antenna = dict(plan.get("antenna") or {})
    scene_plan = dict(plan.get("scene_plan") or {})
    measurement_plane = dict(plan.get("measurement_plane") or {})
    config = dict(plan.get("config") or {})
    physical_cfg = dict(config.get("physical") or {})
    propagation_cfg = dict(config.get("propagation") or {})
    solver_cfg = dict(config.get("solver") or {})
    scene_defaults_cfg = dict(config.get("scene_defaults") or {})
    antenna_cfg = dict(config.get("antenna") or {})

    pos = antenna.get("position_m")
    if not isinstance(pos, list) or len(pos) < 3:
        raise ValueError("engine_plan.antenna.position_m [x, y, z] is required")

    bounds = dict(measurement_plane.get("bounds") or {})
    if not bounds:
        raise ValueError("engine_plan.measurement_plane.bounds is required")
    min_x = float(bounds["min_x"])
    max_x = float(bounds["max_x"])
    min_y = float(bounds["min_y"])
    max_y = float(bounds["max_y"])
    width = max(1.0, max_x - min_x)
    height = max(1.0, max_y - min_y)
    cx = min_x + width / 2.0
    cy = min_y + height / 2.0

    z_plane = float(measurement_plane["z_m"])
    cell_size_m = float(measurement_plane["cell_size_m"])
    max_depth = int(solver_cfg["max_depth"])
    samples_per_tx = int(solver_cfg["samples_per_tx"])
    seed = int(solver_cfg["seed"])

    los = bool(propagation_cfg.get("los", True))
    specular_reflection = bool(propagation_cfg.get("specular_reflection", True))
    refraction = bool(propagation_cfg.get("refraction", True))
    diffuse_reflection = bool(propagation_cfg.get("diffuse_reflection", False))
    diffraction = bool(propagation_cfg.get("diffraction", False))

    with tempfile.TemporaryDirectory(prefix="sionna-rt-") as td:
        mesh_dir = Path(td)
        floor_obj = mesh_dir / "floor.obj"
        _write_floor_obj(floor_obj, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y)

        scene = load_scene(None, merge_shapes=False)

        floor_material_id = str(scene_defaults_cfg.get("floor_material_id", "concrete"))
        floor_thickness_m = float(scene_defaults_cfg.get("floor_thickness_m", 0.05))
        floor_mat = ITURadioMaterial(
            "itu-floor", floor_material_id, thickness=max(1e-4, floor_thickness_m)
        )
        scene_objects = [
            SceneObject(fname=str(floor_obj), name="rf_floor", radio_material=floor_mat),
        ]

        # cache key = (sionna_material_key, effective_thickness_rounded).
        # 기존에는 (sionna_material_key,) 만으로 캐시해서 같은 material 의 첫 thickness 가
        # 이후 모든 wall/opening/furniture에 잘못 재사용되던 잠재적 버그가 있었다 — 같이 해결.
        material_cache: dict[tuple[str, float], Any] = {}
        materials_applied: list[dict[str, Any]] = []
        any_loss_offset_unapplied = False

        def _resolve_material(
            sionna_key: str, effective_thickness: float, name_hint: str
        ) -> Any:
            key = (sionna_key, round(effective_thickness, _MATERIAL_CACHE_PRECISION))
            cached = material_cache.get(key)
            if cached is None:
                cached = ITURadioMaterial(
                    f"itu-{name_hint}",
                    sionna_key,
                    thickness=max(1e-4, effective_thickness),
                )
                material_cache[key] = cached
            return cached

        def _record_correction(
            *,
            kind: str,
            parent_id: str,
            segment_index: int,
            material_id: str,
            sionna_key: str,
            geom_thk: float,
            scale: float,
            eff_thk: float,
            loss_offset_db: float,
            learnable: bool,
        ) -> None:
            nonlocal any_loss_offset_unapplied
            if loss_offset_db != 0.0:
                any_loss_offset_unapplied = True
            materials_applied.append(
                {
                    "kind": kind,
                    "parent_id": parent_id,
                    "segment_index": segment_index,
                    "material_id": material_id,
                    "sionna_material_key": sionna_key,
                    "geometric_thickness_m": geom_thk,
                    "attenuation_scale": scale,
                    "effective_thickness_m": eff_thk,
                    "loss_offset_db": loss_offset_db,
                    "loss_offset_applied": False,
                    "learnable": learnable,
                }
            )

        # ─── walls (with opening splits) ────────────────────────────────────
        all_openings = list(scene_plan.get("openings", []) or [])
        openings_by_wall: dict[str, list[Mapping[str, Any]]] = {}
        for op in all_openings:
            wid = str(op.get("wall_id") or "")
            if wid:
                openings_by_wall.setdefault(wid, []).append(op)

        opening_segment_index: dict[str, int] = {}
        scene_obj_index = 0

        for i, wall in enumerate(scene_plan.get("walls", [])):
            wid = str(wall.get("id", f"wall_{i}"))
            wx1 = float(wall["x1"])
            wy1 = float(wall["y1"])
            wx2 = float(wall["x2"])
            wy2 = float(wall["y2"])
            wth = float(wall["thickness_m"])
            wh = float(wall["height_m"])
            w_dx = wx2 - wx1
            w_dy = wy2 - wy1
            w_len = math.hypot(w_dx, w_dy)
            if w_len <= _SEGMENT_MIN_LENGTH_M:
                continue
            ux, uy = w_dx / w_len, w_dy / w_len

            wall_scale = float(wall.get("attenuation_scale", 1.0))
            wall_loss_off = float(wall.get("loss_offset_db", 0.0))
            wall_learn = bool(wall.get("learnable", False))
            wall_eff_thk = max(1e-4, wth * wall_scale)
            wall_mat_id = str(wall.get("material_id", wall["sionna_material_key"]))
            wall_sionna_key = str(wall["sionna_material_key"])

            # opening 들을 wall 축 따라 [s_start, s_end] 로 변환 (domain validator가 정합성 보장)
            wall_ops = openings_by_wall.get(wid, [])
            op_intervals: list[tuple[float, float, Mapping[str, Any]]] = []
            for op in wall_ops:
                cx = float(op["center_xy"][0])
                cy = float(op["center_xy"][1])
                s_center = ((cx - wx1) * w_dx + (cy - wy1) * w_dy) / w_len
                half = float(op["width_m"]) / 2.0
                s_start = max(0.0, s_center - half)
                s_end = min(w_len, s_center + half)
                if s_end - s_start > _SEGMENT_MIN_LENGTH_M:
                    op_intervals.append((s_start, s_end, op))
            op_intervals.sort(key=lambda x: x[0])

            # 솔리드 wall segment 들을 opening 사이 공간으로 잘라낸다
            cursor = 0.0
            wall_seg_idx = 0
            for s_start, s_end, _op in op_intervals:
                if s_start - cursor > _SEGMENT_MIN_LENGTH_M:
                    sx1, sy1 = wx1 + cursor * ux, wy1 + cursor * uy
                    sx2, sy2 = wx1 + s_start * ux, wy1 + s_start * uy
                    seg_path = mesh_dir / f"wall_{i}_seg{wall_seg_idx}.obj"
                    _write_wall_box_obj(
                        seg_path,
                        x1=sx1, y1=sy1, x2=sx2, y2=sy2,
                        thickness=wth, height=wh,
                    )
                    if seg_path.exists():
                        mat = _resolve_material(
                            wall_sionna_key, wall_eff_thk,
                            f"wall-{wall_sionna_key}-{i}-{wall_seg_idx}",
                        )
                        scene_objects.append(
                            SceneObject(
                                fname=str(seg_path),
                                name=f"rf_wall_{i}_seg{wall_seg_idx}",
                                radio_material=mat,
                            )
                        )
                        _record_correction(
                            kind="wall_segment", parent_id=wid,
                            segment_index=wall_seg_idx,
                            material_id=wall_mat_id, sionna_key=wall_sionna_key,
                            geom_thk=wth, scale=wall_scale, eff_thk=wall_eff_thk,
                            loss_offset_db=wall_loss_off, learnable=wall_learn,
                        )
                        wall_seg_idx += 1
                        scene_obj_index += 1
                cursor = s_end

            # 마지막 segment (마지막 opening 끝 ~ wall 끝)
            if w_len - cursor > _SEGMENT_MIN_LENGTH_M:
                sx1, sy1 = wx1 + cursor * ux, wy1 + cursor * uy
                seg_path = mesh_dir / f"wall_{i}_seg{wall_seg_idx}.obj"
                _write_wall_box_obj(
                    seg_path,
                    x1=sx1, y1=sy1, x2=wx2, y2=wy2,
                    thickness=wth, height=wh,
                )
                if seg_path.exists():
                    mat = _resolve_material(
                        wall_sionna_key, wall_eff_thk,
                        f"wall-{wall_sionna_key}-{i}-{wall_seg_idx}",
                    )
                    scene_objects.append(
                        SceneObject(
                            fname=str(seg_path),
                            name=f"rf_wall_{i}_seg{wall_seg_idx}",
                            radio_material=mat,
                        )
                    )
                    _record_correction(
                        kind="wall_segment", parent_id=wid,
                        segment_index=wall_seg_idx,
                        material_id=wall_mat_id, sionna_key=wall_sionna_key,
                        geom_thk=wth, scale=wall_scale, eff_thk=wall_eff_thk,
                        loss_offset_db=wall_loss_off, learnable=wall_learn,
                    )
                    scene_obj_index += 1

        # ─── opening boxes (door/window) ────────────────────────────────────
        # walls_by_id 다시 빌드 — opening은 자기 wall에서 axis/thickness를 가져온다
        walls_by_id: dict[str, Mapping[str, Any]] = {
            str(w.get("id", "")): w for w in (scene_plan.get("walls") or [])
        }
        for j, op in enumerate(all_openings):
            wall_ref = walls_by_id.get(str(op.get("wall_id", "")))
            if wall_ref is None:
                continue
            wx1 = float(wall_ref["x1"])
            wy1 = float(wall_ref["y1"])
            wx2 = float(wall_ref["x2"])
            wy2 = float(wall_ref["y2"])
            w_dx, w_dy = wx2 - wx1, wy2 - wy1
            w_len = math.hypot(w_dx, w_dy)
            if w_len <= 1e-9:
                continue
            ux, uy = w_dx / w_len, w_dy / w_len
            cx = float(op["center_xy"][0])
            cy = float(op["center_xy"][1])
            s_center = ((cx - wx1) * w_dx + (cy - wy1) * w_dy) / w_len
            half = float(op["width_m"]) / 2.0
            s_start = max(0.0, s_center - half)
            s_end = min(w_len, s_center + half)
            if s_end - s_start <= _SEGMENT_MIN_LENGTH_M:
                continue
            ox1, oy1 = wx1 + s_start * ux, wy1 + s_start * uy
            ox2, oy2 = wx1 + s_end * ux, wy1 + s_end * uy
            box_thk = float(wall_ref["thickness_m"])
            op_height = float(op["height_m"])
            op_bottom_z = float(op["bottom_z_m"])
            op_scale = float(op.get("attenuation_scale", 1.0))
            op_loss_off = float(op.get("loss_offset_db", 0.0))
            op_learn = bool(op.get("learnable", False))
            op_eff_thk = max(1e-4, box_thk * op_scale)
            op_mat_id = str(op.get("material_id", op["sionna_material_key"]))
            op_sionna_key = str(op["sionna_material_key"])
            op_id = str(op.get("id", f"opening_{j}"))
            op_kind = str(op.get("kind", "opening"))

            op_path = mesh_dir / f"opening_{j}_{op_kind}.obj"
            _write_wall_box_obj(
                op_path,
                x1=ox1, y1=oy1, x2=ox2, y2=oy2,
                thickness=box_thk, height=op_height, bottom_z=op_bottom_z,
            )
            if not op_path.exists():
                continue
            mat = _resolve_material(
                op_sionna_key, op_eff_thk, f"opening-{op_sionna_key}-{j}"
            )
            scene_objects.append(
                SceneObject(
                    fname=str(op_path),
                    name=f"rf_opening_{j}_{op_kind}",
                    radio_material=mat,
                )
            )
            _record_correction(
                kind="opening_box", parent_id=op_id,
                segment_index=opening_segment_index.get(op_id, 0),
                material_id=op_mat_id, sionna_key=op_sionna_key,
                geom_thk=box_thk, scale=op_scale, eff_thk=op_eff_thk,
                loss_offset_db=op_loss_off, learnable=op_learn,
            )

        # ─── furniture extrusions ────────────────────────────────────────────
        furniture_default_thk = float(
            scene_defaults_cfg.get("furniture_default_thickness_m", _FURNITURE_DEFAULT_THICKNESS_M)
        )
        for k, fpiece in enumerate(scene_plan.get("furniture", []) or []):
            polygon = fpiece.get("polygon_xy") or []
            if len(polygon) < 3:
                continue
            f_height = float(fpiece.get("height_m", 1.0))
            f_scale = float(fpiece.get("attenuation_scale", 1.0))
            f_loss_off = float(fpiece.get("loss_offset_db", 0.0))
            f_learn = bool(fpiece.get("learnable", False))
            # per-piece radio_thickness_m override → scene_defaults → module fallback
            f_raw_thk = fpiece.get("radio_thickness_m")
            f_radio_thk = float(f_raw_thk) if f_raw_thk is not None else furniture_default_thk
            f_eff_thk = max(1e-4, f_radio_thk * f_scale)
            f_mat_id = str(fpiece.get("material_id", fpiece["sionna_material_key"]))
            f_sionna_key = str(fpiece["sionna_material_key"])
            f_id = str(fpiece.get("id", f"furniture_{k}"))

            f_path = mesh_dir / f"furniture_{k}.obj"
            _write_extruded_polygon_obj(
                f_path, polygon_xy=polygon, height=f_height, bottom_z=0.0,
            )
            if not f_path.exists():
                continue
            mat = _resolve_material(
                f_sionna_key, f_eff_thk, f"furniture-{f_sionna_key}-{k}"
            )
            scene_objects.append(
                SceneObject(
                    fname=str(f_path),
                    name=f"rf_furniture_{k}",
                    radio_material=mat,
                )
            )
            _record_correction(
                kind="furniture_box", parent_id=f_id, segment_index=0,
                material_id=f_mat_id, sionna_key=f_sionna_key,
                geom_thk=f_radio_thk, scale=f_scale,
                eff_thk=f_eff_thk, loss_offset_db=f_loss_off, learnable=f_learn,
            )

        if any_loss_offset_unapplied:
            logger.warning(
                "sionna_runtime: %d scene object(s) carry non-zero loss_offset_db but "
                "the runtime does not apply per-material offsets yet (requires per-cell "
                "material mask). Values are echoed in result.config.materials_applied.",
                sum(1 for m in materials_applied if m["loss_offset_db"] != 0.0),
            )

        scene.edit(add=scene_objects)

        freq_ghz = float(antenna.get("frequency_ghz") or physical_cfg.get("frequency_ghz", 5.0))
        tx_power_dbm = float(
            antenna.get("tx_power_dbm") if antenna.get("tx_power_dbm") is not None
            else physical_cfg.get("tx_power_dbm", 20.0)
        )
        scene.frequency = freq_ghz * 1e9
        scene.tx_array = PlanarArray(
            num_rows=int(antenna_cfg.get("array_rows", 1)),
            num_cols=int(antenna_cfg.get("array_cols", 1)),
            vertical_spacing=float(antenna_cfg.get("vertical_spacing", 0.5)),
            horizontal_spacing=float(antenna_cfg.get("horizontal_spacing", 0.5)),
            pattern=str(antenna_cfg.get("pattern", "iso")),
            polarization=str(antenna_cfg.get("polarization", "V")),
        )
        visualization_cfg = dict(config.get("visualization") or {})
        tx_display_radius = float(
            visualization_cfg.get("tx_display_radius_m", 0.15)
        )
        tx = Transmitter(
            name=str(antenna.get("tx_id", "ap_tx")),
            position=[float(pos[0]), float(pos[1]), float(pos[2])],
            power_dbm=tx_power_dbm,
            display_radius=tx_display_radius,
        )
        scene.add(tx)

        solver = RadioMapSolver()
        solver_kwargs: dict[str, Any] = {
            "scene": scene,
            "center": [cx, cy, z_plane],
            "orientation": [0.0, 0.0, 0.0],
            "size": [width, height],
            "cell_size": [cell_size_m, cell_size_m],
            "samples_per_tx": samples_per_tx,
            "max_depth": max_depth,
            "los": los,
            "specular_reflection": specular_reflection,
            "diffuse_reflection": diffuse_reflection,
            "refraction": refraction,
            "diffraction": diffraction,
            "seed": seed,
        }
        try:
            rm = solver(**solver_kwargs)
        except TypeError as exc:
            # 일부 Sionna 버전은 diffraction 인자를 지원하지 않음. metadata만 남기고 fallback.
            if "diffraction" not in str(exc):
                raise
            solver_kwargs.pop("diffraction", None)
            rm = solver(**solver_kwargs)
        rss_w = _to_numpy(rm.rss)

    while rss_w.ndim > 2:
        rss_w = rss_w[0]
    if rss_w.ndim == 1:
        rss_w = rss_w[np.newaxis, :]
    if rss_w.ndim != 2:
        raise ValueError(f"unexpected radiomap rss shape: {rss_w.shape}")

    rss_dbm = _rss_w_to_dbm(rss_w)
    valid_mask = rss_dbm > INVALID_DBM_THRESHOLD
    valid_values = rss_dbm[valid_mask]
    total_cell_count = int(rss_dbm.size)
    valid_cell_count = int(valid_values.size)
    invalid_cell_count = int(total_cell_count - valid_cell_count)
    valid_ratio = float(valid_cell_count / max(total_cell_count, 1))
    center_y = rss_dbm.shape[0] // 2
    center_x = rss_dbm.shape[1] // 2
    center_dbm, center_valid, center_source = _nearest_valid_cell(rss_dbm, valid_mask, center_y, center_x)
    if valid_values.size == 0:
        rss_summary = {"min": None, "max": None, "mean": None}
    else:
        rss_summary = {
            "min": float(np.min(valid_values)),
            "max": float(np.max(valid_values)),
            "mean": float(np.mean(valid_values)),
        }
    coverage = _coverage_summary(rss_dbm, valid_mask)
    coverage_valid_only = {
        "ge_-67": float(coverage["ge_-67"]),
        "ge_-70": float(coverage["ge_-70"]),
        "ge_-75": float(coverage["ge_-75"]),
    }
    return {
        "engine": "sionna_rt",
        "model": "sionna_rt_radiomap",
        "grid_shape": [int(rss_dbm.shape[0]), int(rss_dbm.shape[1])],
        "radiomap_dbm": rss_dbm.tolist(),
        "bounds_m": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "z": z_plane,
        },
        "config": {
            "physical": {
                "frequency_ghz": freq_ghz,
                "tx_power_dbm": tx_power_dbm,
            },
            "propagation": {
                "los": los,
                "specular_reflection": specular_reflection,
                "refraction": refraction,
                "diffuse_reflection": diffuse_reflection,
                "diffraction": diffraction,
            },
            "solver": {
                "max_depth": max_depth,
                "samples_per_tx": samples_per_tx,
                "seed": seed,
                "cell_size_m": cell_size_m,
            },
            # adapter가 plan에 넣어둔 ResolvedSionnaConfig sub-configs 를 그대로 echo —
            # 이번 실행이 정확히 어떤 값으로 돌았는지 응답에 남기기 위해.
            "scene_defaults": scene_defaults_cfg,
            "antenna": {
                **antenna_cfg,
                # 실제 PlanarArray 호출에 들어간 값 (default fallback 포함)
                "applied": {
                    "array_rows": int(antenna_cfg.get("array_rows", 1)),
                    "array_cols": int(antenna_cfg.get("array_cols", 1)),
                    "pattern": str(antenna_cfg.get("pattern", "iso")),
                    "polarization": str(antenna_cfg.get("polarization", "V")),
                },
            },
            "visualization": visualization_cfg,
            "provenance": dict(config.get("provenance") or {}),
            "materials_applied": materials_applied,
            "deferred_corrections": {
                # 어떤 calibration 필드가 통과는 됐지만 아직 runtime에 적용 안 됐는지.
                "loss_offset_db": any_loss_offset_unapplied,
            },
        },
        "valid_cell_count": valid_cell_count,
        "invalid_cell_count": invalid_cell_count,
        "valid_ratio": valid_ratio,
        "rss_dbm": rss_summary,
        "rss_dbm_valid": rss_summary,
        "center_cell_rss_dbm": center_dbm,
        "center_cell_valid": center_valid,
        "center_cell_source": center_source,
        "coverage_summary": coverage,
        "coverage_summary_valid_only": coverage_valid_only,
        "coverage_thresholds_dbm": [-67, -70, -75],
    }
