"""Sionna RT 런타임 호출 어댑터 (입력 plan 변환 → 실행 → 결과/아티팩트 구조화)."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from app.infrastructure.ai_runtime.sionna_artifacts import (
    INVALID_DBM_THRESHOLD,
    save_geometry_debug_json,
    save_geometry_overlay_png,
    save_radiomap_png,
    save_runtime_result_json,
    save_valid_mask_png,
)
from app.infrastructure.ai_runtime.sionna_geometry import build_room_mask, room_validity_stats
from app.infrastructure.settings import sionna_cell_size_m, sionna_samples_per_tx, sionna_seed
from packages.ai_runtime.sionna_adapter import sionna_input_dto_to_engine_plan
from packages.ai_runtime.sionna_runtime import run_sionna_rt_from_engine_plan


def run_sionna_with_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    sionna_run_id = str(uuid.uuid4())
    engine = str(payload.get("engine", "sionna_rt"))
    run_type = payload.get("run_type", "run")
    floor_id = payload.get("floor_id")
    input_data = payload["input_data"]

    if engine != "sionna_rt":
        raise ValueError("only engine=sionna_rt is supported")

    plan = sionna_input_dto_to_engine_plan(input_data)
    try:
        sionna_result = run_sionna_rt_from_engine_plan(
            plan,
            cell_size_m=sionna_cell_size_m(),
            samples_per_tx=sionna_samples_per_tx(),
            seed=sionna_seed(),
        )
    except ImportError as exc:
        return _failed_response(sionna_run_id, exc, prefix="ImportError")
    except Exception as exc:
        return _failed_response(sionna_run_id, exc, prefix=type(exc).__name__)

    arr = np.asarray(sionna_result["radiomap_dbm"], dtype=float)
    valid_mask = arr > INVALID_DBM_THRESHOLD
    scene_plan = dict(plan.get("scene_plan") or {})
    antenna = dict(plan.get("antenna") or {})
    bounds = dict(sionna_result.get("bounds_m") or {})
    room_mask = build_room_mask(scene_plan, bounds, arr.shape[1], arr.shape[0])

    geometry_debug_payload = _build_geometry_debug_payload(
        sionna_result=sionna_result,
        scene_plan=scene_plan,
        antenna=antenna,
        bounds=bounds,
        valid_mask=valid_mask,
        room_mask=room_mask,
    )

    artifact_paths = {
        "visualization_path": save_radiomap_png(
            sionna_run_id,
            sionna_result["radiomap_dbm"],
            scene_plan=scene_plan,
            antenna=antenna,
            bounds=bounds,
        ),
        "valid_mask_path": save_valid_mask_png(sionna_run_id, valid_mask),
        "geometry_overlay_path": save_geometry_overlay_png(
            sionna_run_id,
            scene_plan=scene_plan,
            antenna=antenna,
            bounds=bounds,
            width=arr.shape[1],
            height=arr.shape[0],
        ),
        "geometry_debug_path": save_geometry_debug_json(sionna_run_id, geometry_debug_payload),
        "runtime_result_path": save_runtime_result_json(sionna_run_id, sionna_result),
    }

    metrics = _build_metrics(sionna_result, run_type=run_type, floor_id=floor_id)
    artifacts = _build_artifacts(sionna_result, artifact_paths, geometry_debug_payload)

    return {
        "sionna_run_id": sionna_run_id,
        "status": "succeeded",
        "metrics": metrics,
        "artifacts": artifacts,
        "output_root": "",
        "manifest": {
            "engine": "sionna_rt",
            "run_type": run_type,
            "floor_id": floor_id,
            "metrics": metrics,
            "artifacts": artifacts,
        },
        "paths": None,
        "error": None,
    }


def _failed_response(sionna_run_id: str, exc: Exception, *, prefix: str) -> dict[str, Any]:
    return {
        "sionna_run_id": sionna_run_id,
        "status": "failed",
        "metrics": {"mode": "sionna_rt_runtime", "error": str(exc)},
        "artifacts": {},
        "output_root": "",
        "manifest": None,
        "paths": None,
        "error": f"{prefix}: {exc}",
    }


def _build_geometry_debug_payload(
    *,
    sionna_result: dict[str, Any],
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    valid_mask: np.ndarray,
    room_mask: np.ndarray,
) -> dict[str, Any]:
    max_wall_h = 0.0
    for wall in scene_plan.get("walls", []):
        try:
            max_wall_h = max(max_wall_h, float(wall.get("height_m", 0.0)))
        except Exception:
            continue
    measurement_plane_z = float(sionna_result.get("bounds_m", {}).get("z", 1.0))
    room_in_valid = np.logical_and(room_mask, valid_mask)
    return {
        "bounds_m": bounds,
        "measurement_plane_z_m": measurement_plane_z,
        "max_wall_height_m": max_wall_h,
        "measurement_plane_inside_wall_height": bool(0.0 <= measurement_plane_z <= max(max_wall_h, 0.0)),
        "grid_shape": sionna_result.get("grid_shape"),
        "valid_cell_count": int(np.count_nonzero(valid_mask)),
        "total_cell_count": int(valid_mask.size),
        "valid_ratio": float(np.count_nonzero(valid_mask) / max(valid_mask.size, 1)),
        "room_mask_cell_count": int(np.count_nonzero(room_mask)),
        "room_mask_valid_cell_count": int(np.count_nonzero(room_in_valid)),
        "room_mask_valid_ratio": float(
            np.count_nonzero(room_in_valid) / max(np.count_nonzero(room_mask), 1)
        ),
        "room_validity": room_validity_stats(scene_plan, bounds, valid_mask),
        "ap_position_m": antenna.get("position_m"),
    }


def _build_metrics(sionna_result: dict[str, Any], *, run_type: Any, floor_id: Any) -> dict[str, Any]:
    return {
        "mode": "sionna_rt_runtime",
        "run_type": run_type,
        "floor_id": floor_id,
        "rssi_summary": sionna_result["rss_dbm"],
        "coverage_summary": sionna_result["coverage_summary"],
        "valid_cell_count": sionna_result.get("valid_cell_count"),
        "invalid_cell_count": sionna_result.get("invalid_cell_count"),
        "valid_ratio": sionna_result.get("valid_ratio"),
    }


def _build_artifacts(
    sionna_result: dict[str, Any],
    paths: dict[str, str | None],
    geometry_debug_payload: dict[str, Any],
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {
        "engine": "sionna_rt",
        "radiomap": {
            "grid_shape": sionna_result["grid_shape"],
            "bounds_m": sionna_result["bounds_m"],
            "values_dbm": sionna_result["radiomap_dbm"],
        },
        "rssi": {
            **sionna_result["rss_dbm"],
            "valid": sionna_result.get("rss_dbm_valid", sionna_result["rss_dbm"]),
            "center_cell_dbm": sionna_result["center_cell_rss_dbm"],
            "center_cell_valid": sionna_result.get("center_cell_valid", True),
            "center_cell_source": sionna_result.get("center_cell_source", "center"),
        },
        "coverage": sionna_result["coverage_summary"],
        "coverage_summary_valid_only": sionna_result.get("coverage_summary_valid_only"),
        "coverage_thresholds_dbm": sionna_result.get("coverage_thresholds_dbm"),
        "valid_cell_count": sionna_result.get("valid_cell_count"),
        "invalid_cell_count": sionna_result.get("invalid_cell_count"),
        "valid_ratio": sionna_result.get("valid_ratio"),
    }
    for key, value in paths.items():
        if value is not None:
            artifacts[key] = value
    artifacts["geometry_debug"] = geometry_debug_payload
    return artifacts
