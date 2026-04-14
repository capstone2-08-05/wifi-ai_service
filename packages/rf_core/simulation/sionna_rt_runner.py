from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np


def _to_numpy(x: Any) -> np.ndarray:
    if hasattr(x, "numpy"):
        return np.asarray(x.numpy())
    return np.asarray(x)


def _rss_w_to_dbm(rss_w: np.ndarray) -> np.ndarray:
    safe = np.maximum(rss_w, 1e-30)
    return 10.0 * np.log10(safe * 1e3)


def _coverage_summary(dbm_map: np.ndarray) -> dict[str, float]:
    flat = dbm_map.reshape(-1)
    if flat.size == 0:
        return {"ge_-67": 0.0, "ge_-70": 0.0, "ge_-75": 0.0}
    return {
        "ge_-67": float(np.mean(flat >= -67.0)),
        "ge_-70": float(np.mean(flat >= -70.0)),
        "ge_-75": float(np.mean(flat >= -75.0)),
    }


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
        for p in points:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                xs.append(float(p[0]))
                ys.append(float(p[1]))

    if not xs or not ys:
        ax, ay = float(antenna_pos[0]), float(antenna_pos[1])
        return (ax - 2.0, ax + 2.0, ay - 2.0, ay + 2.0)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # 안정적인 라디오맵 크기를 위한 최소 패딩
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

    # 바닥 꼭짓점 4개 (반시계)
    a = (x1 + hx, y1 + hy, 0.0)
    b = (x2 + hx, y2 + hy, 0.0)
    c = (x2 - hx, y2 - hy, 0.0)
    d = (x1 - hx, y1 - hy, 0.0)
    # 상단 꼭짓점 4개
    e = (a[0], a[1], height)
    f = (b[0], b[1], height)
    g = (c[0], c[1], height)
    h = (d[0], d[1], height)

    verts = [a, b, c, d, e, f, g, h]
    lines = [f"v {vx:.6f} {vy:.6f} {vz:.6f}" for vx, vy, vz in verts]
    # 6면(삼각형 12개)
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
) -> dict[str, Any]:
    """
    Engine plan을 받아 Sionna RT RadioMap을 실제 계산한다.
    """
    try:
        from sionna.rt import ITURadioMaterial, PlanarArray, RadioMapSolver, SceneObject, Transmitter, load_scene
    except Exception as exc:  # pragma: no cover - 환경 의존
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

    # rss shape이 [H,W] 또는 [1,H,W] 형태일 수 있어 마지막 2축으로 맞춘다.
    if rss_w.ndim > 2:
        rss_w = np.squeeze(rss_w)
    if rss_w.ndim != 2:
        raise ValueError(f"unexpected radiomap rss shape: {rss_w.shape}")

    rss_dbm = _rss_w_to_dbm(rss_w)
    center_dbm = float(rss_dbm[rss_dbm.shape[0] // 2, rss_dbm.shape[1] // 2])
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
        },
        "rss_dbm": {
            "min": float(np.min(rss_dbm)),
            "max": float(np.max(rss_dbm)),
            "mean": float(np.mean(rss_dbm)),
        },
        "center_cell_rss_dbm": center_dbm,
        "coverage_summary": _coverage_summary(rss_dbm),
    }

