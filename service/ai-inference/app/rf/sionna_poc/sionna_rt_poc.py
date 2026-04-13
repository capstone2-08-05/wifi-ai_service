"""
최소 Sionna RT PoC: golden 4×4 m 방(바닥 + 벽 4) + AP 1대 + RadioMap RSS.

**제품 구조:** 사용자 서비스는 **2D floorplan**(heatmap·AP·재질/창문/가구 설명)이 전면이다.
Sionna의 3D 기하·레이트레이싱은 **제거하지 않고**, **내부 precise 검증 엔진**으로 둔다.

- 좌표계: XY 바닥, Z 상향 (baseline AP `point_geom` + `z_m` 와 동일 매핑).
- ITU 재질: 바닥 `concrete`, 벽 `plasterboard`(baseline drywall 대응).
- Baseline과 수치 1:1 일치는 목표가 아님. 동일 입력 축에서 preview vs precise를 비교한다.

의존성: `requirements-sionna-poc.txt`. 미설치 시 import 단계에서 안내 후 종료.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

_RF_ROOT = Path(__file__).resolve().parent.parent
if str(_RF_ROOT) not in sys.path:
    sys.path.insert(0, str(_RF_ROOT))

from golden_fixtures import GOLDEN_CONFIG, GOLDEN_LAYOUT, GOLDEN_SCENE  # noqa: E402

DEFAULT_MESH_DIR = Path(__file__).resolve().parent / "meshes"


def to_jsonable(obj: object) -> object:
    """Dr.Jit Float, numpy scalar 등 JSON이 직렬화 못 하는 타입을 파이썬 기본값으로 변환."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]

    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    try:
        if isinstance(obj, np.generic):
            value = obj.item()
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return value

        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass

    if hasattr(obj, "numpy"):
        try:
            return to_jsonable(obj.numpy())
        except Exception:
            pass

    if hasattr(obj, "item"):
        try:
            value = obj.item()
            if isinstance(value, float) and not math.isfinite(value):
                return None
            return value
        except Exception:
            pass

    try:
        value = float(obj)
        return value if math.isfinite(value) else None
    except Exception:
        pass

    return str(obj)


def _try_import_sionna():
    try:
        import sionna.rt  # noqa: F401
    except ImportError as e:
        print(
            "sionna-rt 가 설치되어 있지 않습니다.\n"
            "  pip install -r requirements-sionna-poc.txt\n"
            f"원인: {e}",
            file=sys.stderr,
        )
        sys.exit(2)


def _tensor_to_numpy(t) -> np.ndarray:
    """drjit / Tensor → numpy (첫 번째 TX 슬라이스)."""
    if hasattr(t, "numpy"):
        arr = t.numpy()
    else:
        arr = np.array(t)
    if arr.ndim >= 3 and arr.shape[0] == 1:
        arr = arr[0]
    return np.asarray(arr, dtype=np.float64)


def rss_w_to_dbm(rss_w: np.ndarray) -> np.ndarray:
    rss_w = np.maximum(rss_w, 1e-30)
    return 10.0 * np.log10(rss_w * 1e3)


def run_baseline_summary() -> dict:
    from baseline_rf_simulator import BaselineRfSimulator
    from rf_models import ApLayout, Scene, SimulationConfig

    scene = Scene.from_dict(GOLDEN_SCENE)
    layout = ApLayout.from_dict(GOLDEN_LAYOUT)
    config = SimulationConfig.from_dict(GOLDEN_CONFIG)
    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()
    rssi = result.strongest_rssi_map
    return {
        "model": "baseline_rf_simulator",
        "note": "벽 없음, 2D 그리드 path loss + 벽손실(0). Sionna PoC(3D RT, 벽/바닥 있음)과 물리 모델이 다름.",
        "grid_shape": list(rssi.shape),
        "rssi_dbm": {
            "min": float(np.min(rssi)),
            "max": float(np.max(rssi)),
            "mean": float(np.mean(rssi)),
        },
        "center_cell_rssi_dbm": float(rssi[rssi.shape[0] // 2, rssi.shape[1] // 2]),
    }


def build_golden_sionna_scene(mesh_dir: Path):
    from sionna.rt import (
        ITURadioMaterial,
        PlanarArray,
        SceneObject,
        Transmitter,
        load_scene,
    )

    scene = load_scene(None, merge_shapes=False)

    mat_floor = ITURadioMaterial(
        "itu-floor",
        "concrete",
        thickness=0.05,
        color=(0.45, 0.45, 0.5),
    )
    mat_wall = ITURadioMaterial(
        "itu-wall",
        "plasterboard",
        thickness=0.12,
        color=(0.85, 0.82, 0.75),
    )

    floor = SceneObject(
        fname=str(mesh_dir / "floor.obj"),
        name="golden_floor",
        radio_material=mat_floor,
    )
    walls = [
        SceneObject(
            fname=str(mesh_dir / name),
            name=name.replace(".obj", ""),
            radio_material=mat_wall,
        )
        for name in ("wall_x0.obj", "wall_x4.obj", "wall_y0.obj", "wall_y4.obj")
    ]
    scene.edit(add=[floor, *walls])

    scene.frequency = float(GOLDEN_LAYOUT["aps"][0]["frequency_ghz"]) * 1e9
    scene.tx_array = PlanarArray(
        num_rows=1,
        num_cols=1,
        vertical_spacing=0.5,
        horizontal_spacing=0.5,
        pattern="iso",
        polarization="V",
    )

    ap = GOLDEN_LAYOUT["aps"][0]
    pos = ap["point_geom"]["coordinates"]
    tx = Transmitter(
        name="ap_golden",
        position=[float(pos[0]), float(pos[1]), float(ap["z_m"])],
        power_dbm=float(ap["tx_power_dbm"]),
        display_radius=0.15,
    )
    scene.add(tx)
    return scene


def run_sionna_radiomap(
    *,
    mesh_dir: Path,
    cell_size_m: float,
    samples_per_tx: int,
    max_depth: int,
    measurement_z_m: float,
    seed: int,
) -> tuple[object, dict]:
    from sionna.rt import RadioMapSolver

    scene = build_golden_sionna_scene(mesh_dir)
    solver = RadioMapSolver()
    # 4 m × 4 m 평면, baseline bounds (0..4, 0..4) 과 동일 extent
    rm = solver(
        scene=scene,
        center=[2.0, 2.0, measurement_z_m],
        orientation=[0.0, 0.0, 0.0],
        size=[4.0, 4.0],
        cell_size=[cell_size_m, cell_size_m],
        samples_per_tx=samples_per_tx,
        max_depth=max_depth,
        los=True,
        specular_reflection=True,
        diffuse_reflection=False,
        refraction=False,
        seed=seed,
    )

    rss = _tensor_to_numpy(rm.rss)
    rss_dbm = rss_w_to_dbm(rss)

    summary = {
        "model": "sionna_rt_radiomap",
        "frequency_ghz": scene.frequency / 1e9,
        "measurement_plane_z_m": measurement_z_m,
        "cell_size_m": cell_size_m,
        "grid_shape": list(rss_dbm.shape),
        "rss_dbm": {
            "min": float(np.min(rss_dbm)),
            "max": float(np.max(rss_dbm)),
            "mean": float(np.mean(rss_dbm)),
        },
        "center_cell_rss_dbm": float(
            rss_dbm[rss_dbm.shape[0] // 2, rss_dbm.shape[1] // 2]
        ),
        "solver": {
            "samples_per_tx": samples_per_tx,
            "max_depth": max_depth,
            "seed": seed,
        },
    }
    return rm, summary


def main() -> None:
    _try_import_sionna()

    parser = argparse.ArgumentParser(description="Sionna RT golden PoC (RadioMap RSS)")
    parser.add_argument(
        "--mesh-dir",
        type=Path,
        default=DEFAULT_MESH_DIR,
        help="floor.obj / wall_*.obj 위치",
    )
    parser.add_argument("--cell-size-m", type=float, default=1.0)
    parser.add_argument(
        "--samples-per-tx",
        type=int,
        default=300_000,
        help="Monte Carlo 샘플 수 (늘리면 안정·느려짐)",
    )
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument(
        "--measurement-z-m",
        type=float,
        default=1.0,
        help="Radio map 수신 평면 높이 [m] (실내 UE 높이 가정)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="요약 JSON 저장 경로",
    )
    args = parser.parse_args()

    baseline = run_baseline_summary()
    _, sionna = run_sionna_radiomap(
        mesh_dir=args.mesh_dir,
        cell_size_m=args.cell_size_m,
        samples_per_tx=args.samples_per_tx,
        max_depth=args.max_depth,
        measurement_z_m=args.measurement_z_m,
        seed=args.seed,
    )

    report = {
        "purpose": (
            "동일 RF 입력 축에서 내부 precise 엔진(Sionna RT)이 RadioMap을 산출하는지 검증. "
            "사용자 UI는 2D heatmap 중심이며 3D 뷰가 전면이 아님."
        ),
        "layout": {
            "room_m": [4.0, 4.0],
            "ap_position_m": [2.0, 2.0, 2.5],
            "materials_itu": {"floor": "concrete", "walls": "plasterboard (drywall 대응)"},
        },
        "baseline_reference": baseline,
        "sionna_radiomap": sionna,
    }

    safe_report = to_jsonable(report)
    text = json.dumps(safe_report, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        with args.out_json.open("w", encoding="utf-8") as f:
            json.dump(safe_report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
