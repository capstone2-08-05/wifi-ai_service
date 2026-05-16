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

# Mitsuba variant 설정 — sionna.rt import 전에 결정.
#   cuda_ad_rgb : GPU (OptiX). Dockerfile NVIDIA_DRIVER_CAPABILITIES 에 'graphics' 필수.
#   llvm_ad_rgb : CPU JIT. 느리지만 의존성 없음.
#
# 중요: mi.set_variant() 는 lazy — 변수만 세팅하고 OptiX 초기화는 첫 ray tracing 호출
# 시점에 일어난다. 그래서 단순히 set_variant 만으로는 GPU 가능 여부 판단 불가.
# 여기선 **실제로 작은 ray tracing 작업을 한 번 돌려서** OptiX 가 살아있는지 확인한 뒤,
# 실패 시 CPU 로 영구 전환한다. 이후 sionna_runtime 호출은 활성 variant 로 동작.
_PREFERRED_VARIANT = os.getenv("MITSUBA_VARIANT", "cuda_ad_rgb")
_FALLBACK_VARIANT = "llvm_ad_rgb"
ACTIVE_MITSUBA_VARIANT = _FALLBACK_VARIANT  # 확정 후 갱신


def _probe_variant(variant: str) -> bool:
    """주어진 variant 로 set_variant + 작은 render 1회 → 실제 OptiX/CPU 초기화까지 확인.

    True 반환 시 그 variant 가 진짜로 동작. False 면 set 또는 render 단계에서 실패.
    """
    try:
        import mitsuba as mi  # type: ignore[import-not-found]

        mi.set_variant(variant)
        # 최소 scene + render 1 spp 로 OptiX/LLVM 백엔드 강제 초기화.
        scene = mi.load_dict(
            {
                "type": "scene",
                "integrator": {"type": "path"},
                "sensor": {
                    "type": "perspective",
                    "film": {"type": "hdrfilm", "width": 2, "height": 2},
                },
                "shape": {"type": "sphere"},
            }
        )
        mi.render(scene, spp=1)
        return True
    except Exception as exc:
        logger.warning("Mitsuba variant probe failed (%s): %s", variant, exc)
        return False


# 라이브러리 버전 로그 — sionna/mitsuba/drjit 호환성 디버깅용.
# Dr.Jit while_loop 같은 내부 에러가 버전 mismatch 일 때 흔히 발생.
try:
    import sionna  # type: ignore[import-not-found]
    import mitsuba as _mi_v  # type: ignore[import-not-found]
    import drjit  # type: ignore[import-not-found]
    logger.info(
        "[RF_DEBUG] sionna=%s mitsuba=%s drjit=%s",
        getattr(sionna, "__version__", "?"),
        getattr(_mi_v, "__version__", "?"),
        getattr(drjit, "__version__", "?"),
    )
except Exception as _vexc:
    logger.warning("[RF_DEBUG] version probe failed: %s", _vexc)


# 1차: 선호 variant (보통 GPU) 실측 → 안 되면 CPU 로 폴백.
if _probe_variant(_PREFERRED_VARIANT):
    ACTIVE_MITSUBA_VARIANT = _PREFERRED_VARIANT
    logger.info("Mitsuba variant: %s (preferred, probed OK)", _PREFERRED_VARIANT)
elif _PREFERRED_VARIANT != _FALLBACK_VARIANT and _probe_variant(_FALLBACK_VARIANT):
    ACTIVE_MITSUBA_VARIANT = _FALLBACK_VARIANT
    logger.warning(
        "Mitsuba %s probe failed — using %s (CPU) for the rest of this process",
        _PREFERRED_VARIANT, _FALLBACK_VARIANT,
    )
else:
    logger.error(
        "Both Mitsuba variants failed to initialize. sionna.rt will fail at first call.",
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

    # === 입력 scene 디버그 dump — Sionna 가 죽을 때 원인 추적용 ===========
    raw_walls = scene_dict.get("walls") or []
    raw_rooms = scene_dict.get("rooms") or []
    logger.info(
        "[RF_DEBUG] num_aps=%d num_walls(raw)=%d num_rooms(raw)=%d mitsuba=%s",
        len(parsed.access_points), len(raw_walls), len(raw_rooms),
        ACTIVE_MITSUBA_VARIANT,
    )
    logger.info(
        "[RF_DEBUG] sim freq_Hz=%.0f tx_dBm=%.1f res_m=%.3f max_depth=%d "
        "samples_per_tx=%d measurement_z_m=%.2f",
        sim.frequency_hz, sim.tx_power_dbm, sim.resolution_m, sim.max_depth,
        sim.samples_per_tx, sim.measurement_plane_z_m,
    )
    for i, ap in enumerate(parsed.access_points[:5]):
        logger.info(
            "[RF_DEBUG] ap[%d] id=%s pos=(%.3f, %.3f, %.3f)",
            i, ap.id, ap.x_m, ap.y_m, ap.z_m,
        )
    for i, w in enumerate(raw_walls[:8]):
        logger.info("[RF_DEBUG] wall[%d] %s", i, w)
    if raw_rooms:
        logger.info(
            "[RF_DEBUG] room[0] points_count=%d sample=%s",
            len(raw_rooms[0].get("points") or []),
            (raw_rooms[0].get("points") or [])[:3],
        )

    for ap in parsed.access_points:
        plan = _build_engine_plan(scene_dict, ap, sim)
        # 변환된 plan 의 wall/room 개수도 한 번 더 확인 (필터링 후 남은 수).
        plan_walls = plan.get("scene_plan", {}).get("walls", [])
        plan_rooms = plan.get("scene_plan", {}).get("rooms", [])
        logger.info(
            "[RF_DEBUG] engine_plan ap=%s plan_walls=%d plan_rooms=%d",
            ap.id, len(plan_walls), len(plan_rooms),
        )
        logger.info(
            "Sionna RT start ap_id=%s freq_GHz=%.3f res_m=%.3f max_depth=%d",
            ap.id, sim.frequency_hz / 1e9, sim.resolution_m, sim.max_depth,
        )
        try:
            rt_out = run_sionna_rt_from_engine_plan(
                plan,
                cell_size_m=float(sim.resolution_m),
                samples_per_tx=int(sim.samples_per_tx),
                seed=int(sim.seed),
            )
        except Exception:
            # CloudWatch 에 full traceback 을 남겨야 진짜 원인이 보임.
            # handler 가 위에서 다시 wrap 하기 전에 raw exc 를 여기서 먼저 기록.
            logger.exception(
                "[RF_ERROR] run_sionna_rt_from_engine_plan failed ap=%s "
                "(variant=%s, walls=%d, samples=%d, max_depth=%d)",
                ap.id, ACTIVE_MITSUBA_VARIANT, len(plan_walls),
                sim.samples_per_tx, sim.max_depth,
            )
            raise
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
