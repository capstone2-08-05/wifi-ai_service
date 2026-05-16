"""Sionna RT 실행 래퍼.

`packages/ai_runtime/sionna_runtime.py` 의 `run_sionna_rt_from_engine_plan` 을 호출하면서
input.json 의 access_points 와 simulation 파라미터를 `engine_plan` 형식으로 어댑트한다.

여러 AP 가 있으면 AP 별로 시뮬을 돌리고, 셀별 dBm 의 max 를 취해서 "best signal" radio map 으로 집계.

Mitsuba/Sionna variant 선택:
  - 기본은 LLVM CPU variant — OptiX(NVIDIA GPU ray tracing) 의존성 없이 어떤 인스턴스에서도 동작.
    GPU 인스턴스 + OptiX SDK 가 컨테이너에 포함된 경우에만 cuda_ad_rgb 사용 가능.
  - `MITSUBA_VARIANT` env 로 override (예: `cuda_ad_rgb`).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

from app.constants import INVALID_DBM_THRESHOLD
from app.contracts import AccessPoint, ParsedInput, SimulationParams

logger = logging.getLogger(__name__)

# Mitsuba variant 를 sionna.rt import 전에 강제 — OptiX 초기화 실패 회피.
# `cuda_ad_rgb` 는 NVIDIA OptiX SDK 가 컨테이너에 있어야 동작.
# `llvm_ad_rgb` 는 CPU JIT (LLVM) — 느리지만 의존성 없음.
_MITSUBA_VARIANT = os.getenv("MITSUBA_VARIANT", "llvm_ad_rgb")
try:
    import mitsuba as mi  # type: ignore[import-not-found]

    mi.set_variant(_MITSUBA_VARIANT)
    logger.info("Mitsuba variant set to %s", _MITSUBA_VARIANT)
except Exception as exc:
    logger.warning(
        "Mitsuba variant set to %s failed (%s) — sionna.rt may pick its default",
        _MITSUBA_VARIANT, exc,
    )


def default_device() -> str:
    """기본 디바이스 hint (관측용). 실제 실행은 sionna 가 결정."""
    forced = os.getenv("DEFAULT_DEVICE", "auto").lower()
    if forced in {"cpu", "cuda", "cuda:0"}:
        return forced
    # auto: GPU 가용성 확인
    try:
        import tensorflow as tf
        if tf.config.list_physical_devices("GPU"):
            return "cuda:0"
    except Exception:
        pass
    return "cpu"


def sionna_version_str() -> str:
    try:
        import sionna
        return getattr(sionna, "__version__", "")
    except Exception:
        return ""


def _build_engine_plan(
    scene_dict: dict[str, Any],
    ap: AccessPoint,
    sim: SimulationParams,
) -> dict[str, Any]:
    """input.simulation + scene.json + 단일 AP → sionna_runtime 의 engine_plan."""
    return {
        "antenna": {
            "tx_id": ap.id,
            "position_m": [float(ap.x_m), float(ap.y_m), float(ap.z_m)],
            "frequency_ghz": float(sim.frequency_hz) / 1e9,
            "tx_power_dbm": float(sim.tx_power_dbm),
        },
        "scene_plan": _scene_to_plan(scene_dict),
        "solver": {
            "measurement_plane_z_m": float(sim.measurement_plane_z_m),
            "max_depth": int(sim.max_depth),
        },
    }


def _scene_to_plan(scene_dict: dict[str, Any]) -> dict[str, Any]:
    """SceneSchema dict → sionna_runtime 이 기대하는 scene_plan (벽/룸).

    sionna_runtime 은 wall: {x1,y1,x2,y2,thickness_m,height_m,itu_radio_material}
    room: {points: [[x,y],...]} 형식을 받는다. SceneSchema 의 walls 는
    {x1,y1,x2,y2,thickness,height,material} 라서 키 이름만 맞춰주면 됨.
    """
    walls_out: list[dict[str, Any]] = []
    for w in scene_dict.get("walls") or []:
        try:
            walls_out.append(
                {
                    "x1": float(w["x1"]),
                    "y1": float(w["y1"]),
                    "x2": float(w["x2"]),
                    "y2": float(w["y2"]),
                    "thickness_m": float(w.get("thickness", w.get("thickness_m", 0.12))),
                    "height_m": float(w.get("height", w.get("height_m", 2.6))),
                    "itu_radio_material": str(w.get("material", "plasterboard")),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    rooms_out: list[dict[str, Any]] = []
    for r in scene_dict.get("rooms") or []:
        pts = r.get("points")
        if isinstance(pts, list):
            rooms_out.append({"points": pts})

    return {"walls": walls_out, "rooms": rooms_out}


def run_simulation_for_all_aps(
    parsed: ParsedInput,
    scene_dict: dict[str, Any],
) -> dict[str, Any]:
    """AP 별 시뮬 실행 → 셀별 max dBm 집계.

    반환:
      {
        "radio_map_dbm": np.ndarray (rows, cols),
        "bounds_m": {min_x, max_x, min_y, max_y, z},
        "cell_size_m": float,
        "grid_shape": [rows, cols],
        "valid_cell_count": int,
        "invalid_cell_count": int,
        "valid_ratio": float,
        "rss_dbm": {min, max, mean},
        "coverage_summary": {...},
      }
    """
    from packages.ai_runtime.sionna_runtime import run_sionna_rt_from_engine_plan

    sim = parsed.simulation
    aggregate_db: np.ndarray | None = None
    last_meta: dict[str, Any] = {}

    for ap in parsed.access_points:
        plan = _build_engine_plan(scene_dict, ap, sim)
        logger.info(
            "Sionna RT start ap_id=%s freq_GHz=%.3f res_m=%.3f max_depth=%d",
            ap.id, sim.frequency_hz / 1e9, sim.resolution_m, sim.max_depth,
        )
        rt_out = run_sionna_rt_from_engine_plan(
            plan,
            cell_size_m=float(sim.resolution_m),
            samples_per_tx=int(sim.samples_per_tx),
            seed=int(sim.seed),
        )
        dbm = np.asarray(rt_out["radiomap_dbm"], dtype=np.float32)

        if aggregate_db is None:
            aggregate_db = dbm
        else:
            # 모양이 같다는 보장은 같은 scene + 같은 res 이므로 동일.
            if aggregate_db.shape != dbm.shape:
                logger.warning(
                    "radio map shape mismatch across APs (%s vs %s); skip aggregation",
                    aggregate_db.shape, dbm.shape,
                )
            else:
                aggregate_db = np.maximum(aggregate_db, dbm)
        last_meta = rt_out

    assert aggregate_db is not None  # access_points minItems=1 보장

    valid_mask = aggregate_db > INVALID_DBM_THRESHOLD
    valid_values = aggregate_db[valid_mask]
    valid_count = int(valid_values.size)
    total_count = int(aggregate_db.size)
    invalid_count = int(total_count - valid_count)

    if valid_count == 0:
        rss_summary = {"min": None, "max": None, "mean": None}
    else:
        rss_summary = {
            "min": float(np.min(valid_values)),
            "max": float(np.max(valid_values)),
            "mean": float(np.mean(valid_values)),
        }

    coverage = {
        "ge_-67": float(np.mean(valid_values >= -67.0)) if valid_count else 0.0,
        "ge_-70": float(np.mean(valid_values >= -70.0)) if valid_count else 0.0,
        "ge_-75": float(np.mean(valid_values >= -75.0)) if valid_count else 0.0,
        "valid_cell_count": valid_count,
        "total_cell_count": total_count,
        "valid_cell_ratio": float(valid_count / max(total_count, 1)),
    }

    return {
        "radio_map_dbm": aggregate_db,
        "bounds_m": dict(last_meta.get("bounds_m") or {}),
        "cell_size_m": float(sim.resolution_m),
        "grid_shape": [int(aggregate_db.shape[0]), int(aggregate_db.shape[1])],
        "valid_cell_count": valid_count,
        "invalid_cell_count": invalid_count,
        "valid_ratio": float(valid_count / max(total_count, 1)),
        "rss_dbm": rss_summary,
        "coverage_summary": coverage,
        "engine": last_meta.get("engine", "sionna_rt"),
    }
