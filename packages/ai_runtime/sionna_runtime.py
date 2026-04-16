from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

INVALID_DBM_THRESHOLD = -200.0


def _resolve_target_device(preferred_device: str, default_device: str) -> str:
    preferred = (preferred_device or "").strip().lower()
    if preferred and preferred != "auto":
        if preferred in {"gpu", "cuda"} or preferred.startswith("cuda"):
            return "cuda"
        return "cpu"

    configured = (default_device or "auto").strip().lower()
    if configured == "cpu":
        return "cpu"
    if configured in {"gpu", "cuda"} or configured.startswith("cuda"):
        return "cuda"
    return "auto"


def _select_runtime_backend(preferred_device: str, default_device: str) -> dict[str, Any]:
    try:
        import drjit as dr
        import mitsuba as mi
    except Exception as exc:
        raise RuntimeError("Failed to import Dr.Jit/Mitsuba runtime backends") from exc

    requested = _resolve_target_device(preferred_device, default_device)
    if requested == "cpu":
        candidates = [("cpu", "llvm_ad_mono_polarized")]
    elif requested == "cuda":
        candidates = [("cuda", "cuda_ad_mono_polarized"), ("cpu", "llvm_ad_mono_polarized")]
    else:
        candidates = [("cuda", "cuda_ad_mono_polarized"), ("cpu", "llvm_ad_mono_polarized")]

    errors: list[str] = []
    for device_name, variant in candidates:
        if device_name == "cuda" and not bool(dr.has_backend(dr.JitBackend.CUDA)):
            errors.append("cuda backend unavailable in Dr.Jit")
            continue
        try:
            mi.set_variant(variant)
            return {
                "requested_device": requested,
                "selected_device": device_name,
                "mitsuba_variant": mi.variant(),
                "fallback_used": device_name != "cuda" and requested in {"cuda", "auto"},
            }
        except Exception as exc:
            errors.append(f"{variant}: {exc}")

    raise RuntimeError(f"Unable to select Sionna runtime backend ({'; '.join(errors)})")


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


def _scene_bounds(scene_plan: Mapping[str, Any], antenna_pos: list[float]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    for wall in scene_plan.get("walls", []):
        try:
            xs.extend([float(wall["x1"]), float(wall["x2"])])
            ys.extend([float(wall["y1"]), float(wall["y2"])])
        except Exception:
            continue

    for room in scene_plan.get("rooms", []):
        points = room.get("points")
        if not isinstance(points, list):
            continue
        for point in points:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                xs.append(float(point[0]))
                ys.append(float(point[1]))

    if not xs or not ys:
        ax, ay = float(antenna_pos[0]), float(antenna_pos[1])
        return (ax - 2.0, ax + 2.0, ay - 2.0, ay + 2.0)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad = 0.5
    if math.isclose(min_x, max_x):
        min_x -= 1.0
        max_x += 1.0
    if math.isclose(min_y, max_y):
        min_y -= 1.0
        max_y += 1.0
    return (min_x - pad, max_x + pad, min_y - pad, max_y + pad)


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


def run_sionna_rt_from_engine_plan(
    plan: Mapping[str, Any],
    *,
    cell_size_m: float = 0.5,
    samples_per_tx: int = 100_000,
    seed: int = 42,
    preferred_device: str = "",
    default_device: str = "auto",
) -> dict[str, Any]:
    backend_info = _select_runtime_backend(preferred_device, default_device)
    try:
        from sionna.rt import ITURadioMaterial, PlanarArray, RadioMapSolver, SceneObject, Transmitter, load_scene
    except Exception as exc:
        raise ImportError(
            "Sionna runtime is not available. Install runtime dependencies for sionna.rt."
        ) from exc

    antenna = dict(plan.get("antenna") or {})
    scene_plan = dict(plan.get("scene_plan") or {})
    solver_cfg = dict(plan.get("solver") or {})

    pos = antenna.get("position_m")
    if not isinstance(pos, list) or len(pos) < 3:
        raise ValueError("engine_plan.antenna.position_m [x, y, z] is required")

    min_x, max_x, min_y, max_y = _scene_bounds(scene_plan, pos)
    width = max(1.0, float(max_x - min_x))
    height = max(1.0, float(max_y - min_y))
    cx = min_x + width / 2.0
    cy = min_y + height / 2.0
    z_plane = float(solver_cfg.get("measurement_plane_z_m", 1.0))
    max_depth = int(solver_cfg.get("max_depth", 3))

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
            try:
                wx1 = float(wall["x1"])
                wy1 = float(wall["y1"])
                wx2 = float(wall["x2"])
                wy2 = float(wall["y2"])
                wth = max(0.01, float(wall.get("thickness_m", 0.12)))
                wh = max(0.5, float(wall.get("height_m", 2.6)))
            except Exception:
                continue
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
            itu_name = str(wall.get("itu_radio_material", "plasterboard"))
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

        freq_ghz = float(antenna.get("frequency_ghz", 5.0))
        tx_power_dbm = float(antenna.get("tx_power_dbm", 20.0))
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
        rm = solver(
            scene=scene,
            center=[cx, cy, z_plane],
            orientation=[0.0, 0.0, 0.0],
            size=[width, height],
            cell_size=[float(cell_size_m), float(cell_size_m)],
            samples_per_tx=int(samples_per_tx),
            max_depth=max_depth,
            los=True,
            specular_reflection=True,
            diffuse_reflection=False,
            refraction=False,
            seed=int(seed),
        )
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
            "min_x": float(min_x),
            "max_x": float(max_x),
            "min_y": float(min_y),
            "max_y": float(max_y),
            "z": float(z_plane),
        },
        "solver": {
            "cell_size_m": float(cell_size_m),
            "samples_per_tx": int(samples_per_tx),
            "max_depth": int(max_depth),
            "seed": int(seed),
            "measurement_plane_z_m": float(z_plane),
            "runtime_backend": backend_info,
        },
        "runtime_backend": backend_info,
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
