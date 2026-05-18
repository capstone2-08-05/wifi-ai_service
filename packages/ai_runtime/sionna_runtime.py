from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

INVALID_DBM_THRESHOLD = -200.0


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
) -> None:
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return
    nx = -dy / length
    ny = dx / length
    hx = nx * (thickness / 2.0)
    hy = ny * (thickness / 2.0)

    a = (x1 + hx, y1 + hy, 0.0)
    b = (x2 + hx, y2 + hy, 0.0)
    c = (x2 - hx, y2 - hy, 0.0)
    d = (x1 - hx, y1 - hy, 0.0)
    e = (a[0], a[1], height)
    f = (b[0], b[1], height)
    g = (c[0], c[1], height)
    h = (d[0], d[1], height)

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

        floor_mat = ITURadioMaterial("itu-floor", "concrete", thickness=0.05)
        scene_objects = [
            SceneObject(fname=str(floor_obj), name="rf_floor", radio_material=floor_mat),
        ]

        wall_material_cache: dict[str, Any] = {}
        for i, wall in enumerate(scene_plan.get("walls", [])):
            wx1 = float(wall["x1"])
            wy1 = float(wall["y1"])
            wx2 = float(wall["x2"])
            wy2 = float(wall["y2"])
            wth = float(wall["thickness_m"])
            wh = float(wall["height_m"])
            wall_obj = mesh_dir / f"wall_{i}.obj"
            _write_wall_box_obj(
                wall_obj,
                x1=wx1,
                y1=wy1,
                x2=wx2,
                y2=wy2,
                thickness=wth,
                height=wh,
            )
            if not wall_obj.exists():
                continue
            itu_name = str(wall["sionna_material_key"])
            if itu_name not in wall_material_cache:
                wall_material_cache[itu_name] = ITURadioMaterial(
                    f"itu-wall-{itu_name}-{i}",
                    itu_name,
                    thickness=wth,
                )
            scene_objects.append(
                SceneObject(
                    fname=str(wall_obj),
                    name=f"rf_wall_{i}",
                    radio_material=wall_material_cache[itu_name],
                )
            )

        scene.edit(add=scene_objects)

        freq_ghz = float(antenna.get("frequency_ghz") or physical_cfg.get("frequency_ghz", 5.0))
        tx_power_dbm = float(
            antenna.get("tx_power_dbm") if antenna.get("tx_power_dbm") is not None
            else physical_cfg.get("tx_power_dbm", 20.0)
        )
        scene.frequency = freq_ghz * 1e9
        scene.tx_array = PlanarArray(
            num_rows=1,
            num_cols=1,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern="iso",
            polarization="V",
        )
        tx = Transmitter(
            name=str(antenna.get("tx_id", "ap_tx")),
            position=[float(pos[0]), float(pos[1]), float(pos[2])],
            power_dbm=tx_power_dbm,
            display_radius=0.15,
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
