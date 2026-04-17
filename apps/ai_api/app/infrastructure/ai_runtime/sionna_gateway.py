from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from app.infrastructure.settings import OUTPUT_DIR, sionna_cell_size_m, sionna_samples_per_tx, sionna_seed
from packages.ai_runtime.sionna_adapter import sionna_input_dto_to_engine_plan
from packages.ai_runtime.sionna_runtime import run_sionna_rt_from_engine_plan

INVALID_DBM_THRESHOLD = -200.0


def _resolve_auto_color_limits(valid_values: np.ndarray) -> tuple[float, float]:
    if valid_values.size == 0:
        return (-90.0, -30.0)
    p5, p95 = np.percentile(valid_values, [5.0, 95.0])
    if not np.isfinite(p5) or not np.isfinite(p95):
        return (-90.0, -30.0)
    if float(p95 - p5) < 8.0:
        mid = float(np.mean(valid_values))
        return (mid - 4.0, mid + 4.0)
    return (float(p5), float(p95))


def _to_grid_xy(x: float, y: float, bounds: dict[str, Any], width: int, height: int) -> tuple[float, float]:
    min_x = float(bounds.get("min_x", 0.0))
    max_x = float(bounds.get("max_x", 1.0))
    min_y = float(bounds.get("min_y", 0.0))
    max_y = float(bounds.get("max_y", 1.0))
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    gx = (float(x) - min_x) / span_x * max(width - 1, 1)
    gy = (float(y) - min_y) / span_y * max(height - 1, 1)
    return gx, gy


def _to_world_xy(gx: float, gy: float, bounds: dict[str, Any], width: int, height: int) -> tuple[float, float]:
    min_x = float(bounds.get("min_x", 0.0))
    max_x = float(bounds.get("max_x", 1.0))
    min_y = float(bounds.get("min_y", 0.0))
    max_y = float(bounds.get("max_y", 1.0))
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    wx = min_x + float(gx) / max(width, 1) * span_x
    wy = min_y + float(gy) / max(height, 1) * span_y
    return wx, wy


def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / max(yj - yi, 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _build_room_mask(scene_plan: dict[str, Any], bounds: dict[str, Any], width: int, height: int) -> np.ndarray:
    room_mask = np.zeros((height, width), dtype=bool)
    for room in scene_plan.get("rooms", []):
        points = room.get("points")
        if not isinstance(points, list) or len(points) < 3:
            continue
        polygon: list[tuple[float, float]] = []
        for p in points:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    polygon.append((float(p[0]), float(p[1])))
                except Exception:
                    continue
        if len(polygon) < 3:
            continue
        for gy in range(height):
            for gx in range(width):
                wx, wy = _to_world_xy(gx + 0.5, gy + 0.5, bounds, width, height)
                if _point_in_polygon(wx, wy, polygon):
                    room_mask[gy, gx] = True
    return room_mask


def _room_validity_stats(
    scene_plan: dict[str, Any],
    bounds: dict[str, Any],
    valid_mask: np.ndarray,
) -> dict[str, Any]:
    height, width = valid_mask.shape
    room_stats: list[dict[str, Any]] = []
    total_room_cells = 0
    total_valid_in_rooms = 0
    for room in scene_plan.get("rooms", []):
        rid = str(room.get("id", "room"))
        points = room.get("points")
        if not isinstance(points, list) or len(points) < 3:
            continue
        polygon: list[tuple[float, float]] = []
        for p in points:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    polygon.append((float(p[0]), float(p[1])))
                except Exception:
                    continue
        if len(polygon) < 3:
            continue
        mask = np.zeros((height, width), dtype=bool)
        for gy in range(height):
            for gx in range(width):
                wx, wy = _to_world_xy(gx + 0.5, gy + 0.5, bounds, width, height)
                if _point_in_polygon(wx, wy, polygon):
                    mask[gy, gx] = True
        room_cells = int(np.count_nonzero(mask))
        valid_cells = int(np.count_nonzero(np.logical_and(mask, valid_mask)))
        total_room_cells += room_cells
        total_valid_in_rooms += valid_cells
        room_stats.append(
            {
                "room_id": rid,
                "room_cell_count": room_cells,
                "valid_cell_count": valid_cells,
                "valid_ratio": float(valid_cells / max(room_cells, 1)),
            }
        )
    return {
        "rooms": room_stats,
        "room_total_cell_count": total_room_cells,
        "room_total_valid_cell_count": total_valid_in_rooms,
        "room_total_valid_ratio": float(total_valid_in_rooms / max(total_room_cells, 1)),
    }


def _draw_scene_overlay(
    ax: Any,
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    width: int,
    height: int,
) -> None:
    for wall in scene_plan.get("walls", []):
        try:
            x1, y1 = _to_grid_xy(float(wall["x1"]), float(wall["y1"]), bounds, width, height)
            x2, y2 = _to_grid_xy(float(wall["x2"]), float(wall["y2"]), bounds, width, height)
        except Exception:
            continue
        ax.plot([x1, x2], [y1, y2], color="white", linewidth=1.2, alpha=0.9)

    for opening in scene_plan.get("openings", []):
        try:
            x1, y1 = _to_grid_xy(float(opening["x1"]), float(opening["y1"]), bounds, width, height)
            x2, y2 = _to_grid_xy(float(opening["x2"]), float(opening["y2"]), bounds, width, height)
        except Exception:
            continue
        ax.plot([x1, x2], [y1, y2], color="#35d4ff", linewidth=1.4, linestyle="--", alpha=0.95)

    for room in scene_plan.get("rooms", []):
        center = room.get("center")
        if not (isinstance(center, list) and len(center) >= 2):
            continue
        rid = str(room.get("id", "")).strip()
        if not rid:
            continue
        try:
            cx, cy = _to_grid_xy(float(center[0]), float(center[1]), bounds, width, height)
        except Exception:
            continue
        ax.text(cx, cy, rid, color="white", fontsize=6, ha="center", va="center", alpha=0.9)

    pos = antenna.get("position_m")
    if isinstance(pos, list) and len(pos) >= 2:
        try:
            tx, ty = _to_grid_xy(float(pos[0]), float(pos[1]), bounds, width, height)
            ax.scatter([tx], [ty], marker="*", s=90, c="#00ffd0", edgecolors="black", linewidths=0.8, zorder=5)
        except Exception:
            pass

    legend_handles = [
        Line2D([0], [0], color="white", linewidth=1.2, label="Wall"),
        Line2D([0], [0], color="#35d4ff", linewidth=1.4, linestyle="--", label="Opening"),
        Line2D([0], [0], marker="*", markersize=10, markerfacecolor="#00ffd0", markeredgecolor="black", linewidth=0, label="AP"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=7, framealpha=0.75)


def _save_radiomap_png(
    sionna_run_id: str,
    radiomap_dbm: list[list[float]],
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
) -> str | None:
    try:
        arr = np.asarray(radiomap_dbm, dtype=float)
        valid_values = arr[arr > INVALID_DBM_THRESHOLD]
        vmin, vmax = _resolve_auto_color_limits(valid_values)
        masked = np.ma.masked_where(arr <= INVALID_DBM_THRESHOLD, arr)
        out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "radiomap_heatmap.png"
        fig, ax = plt.subplots(figsize=(7.2, 5.4))
        cmap = plt.get_cmap("inferno").copy()
        cmap.set_bad(color="#5a5a5a", alpha=1.0)
        im = ax.imshow(
            masked,
            origin="lower",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            interpolation="bicubic",
        )
        _draw_scene_overlay(
            ax,
            scene_plan=scene_plan,
            antenna=antenna,
            bounds=bounds,
            width=arr.shape[1],
            height=arr.shape[0],
        )
        ax.set_title("Sionna RT RadioMap")
        ax.set_xlabel("X grid")
        ax.set_ylabel("Y grid")
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label(f"RSS (dBm), auto scale p5-p95 [{vmin:.1f}, {vmax:.1f}]")
        fig.text(0.02, 0.01, "Gray = not simulated / invalid cell", fontsize=8, color="#444444")
        plt.tight_layout()
        plt.savefig(out_path, dpi=150)
        plt.close(fig)
        return str(Path(out_path).resolve())
    except Exception:
        return None


def _save_valid_mask_png(sionna_run_id: str, valid_mask: np.ndarray) -> str | None:
    try:
        out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "valid_mask.png"
        fig, ax = plt.subplots(figsize=(7.2, 5.4))
        ax.imshow(valid_mask.astype(float), origin="lower", cmap="gray", vmin=0.0, vmax=1.0, interpolation="nearest")
        ax.set_title("Valid Cell Mask (white=valid)")
        ax.set_xlabel("X grid")
        ax.set_ylabel("Y grid")
        ax.legend(
            handles=[
                Patch(facecolor="white", edgecolor="black", label="Valid"),
                Patch(facecolor="black", edgecolor="black", label="Invalid"),
            ],
            loc="upper right",
            fontsize=7,
            framealpha=0.75,
        )
        plt.tight_layout()
        plt.savefig(out_path, dpi=140)
        plt.close(fig)
        return str(out_path.resolve())
    except Exception:
        return None


def _save_geometry_overlay_png(
    sionna_run_id: str,
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    width: int,
    height: int,
) -> str | None:
    try:
        out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "geometry_overlay.png"
        fig, ax = plt.subplots(figsize=(7.2, 5.4))
        base = np.zeros((height, width), dtype=float)
        ax.imshow(base, origin="lower", cmap="gray", vmin=0.0, vmax=1.0)
        _draw_scene_overlay(
            ax,
            scene_plan=scene_plan,
            antenna=antenna,
            bounds=bounds,
            width=width,
            height=height,
        )
        ax.set_title("Geometry Debug Overlay")
        ax.set_xlabel("X grid")
        ax.set_ylabel("Y grid")
        plt.tight_layout()
        plt.savefig(out_path, dpi=140)
        plt.close(fig)
        return str(out_path.resolve())
    except Exception:
        return None


def _save_geometry_debug_json(sionna_run_id: str, payload: dict[str, Any]) -> str | None:
    try:
        out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "geometry_debug.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path.resolve())
    except Exception:
        return None


def _save_runtime_result_json(sionna_run_id: str, runtime_result: dict[str, Any]) -> str | None:
    try:
        out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "runtime_result.json"
        out_path.write_text(json.dumps(runtime_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path.resolve())
    except Exception:
        return None


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
        return {
            "sionna_run_id": sionna_run_id,
            "status": "failed",
            "metrics": {"mode": "sionna_rt_runtime", "error": str(exc)},
            "artifacts": {},
            "output_root": "",
            "manifest": None,
            "paths": None,
            "error": f"ImportError: {exc}",
        }
    except Exception as exc:
        return {
            "sionna_run_id": sionna_run_id,
            "status": "failed",
            "metrics": {"mode": "sionna_rt_runtime", "error": str(exc)},
            "artifacts": {},
            "output_root": "",
            "manifest": None,
            "paths": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    arr = np.asarray(sionna_result["radiomap_dbm"], dtype=float)
    valid_mask = arr > INVALID_DBM_THRESHOLD
    scene_plan = dict(plan.get("scene_plan") or {})
    antenna = dict(plan.get("antenna") or {})
    bounds = dict(sionna_result.get("bounds_m") or {})
    room_mask = _build_room_mask(scene_plan, bounds, arr.shape[1], arr.shape[0])
    room_valid_stats = _room_validity_stats(scene_plan, bounds, valid_mask)
    max_wall_h = 0.0
    for wall in scene_plan.get("walls", []):
        try:
            max_wall_h = max(max_wall_h, float(wall.get("height_m", 0.0)))
        except Exception:
            continue
    measurement_plane_z = float(sionna_result.get("bounds_m", {}).get("z", 1.0))
    geometry_debug_payload = {
        "bounds_m": bounds,
        "measurement_plane_z_m": measurement_plane_z,
        "max_wall_height_m": max_wall_h,
        "measurement_plane_inside_wall_height": bool(0.0 <= measurement_plane_z <= max(max_wall_h, 0.0)),
        "grid_shape": sionna_result.get("grid_shape"),
        "valid_cell_count": int(np.count_nonzero(valid_mask)),
        "total_cell_count": int(valid_mask.size),
        "valid_ratio": float(np.count_nonzero(valid_mask) / max(valid_mask.size, 1)),
        "room_mask_cell_count": int(np.count_nonzero(room_mask)),
        "room_mask_valid_cell_count": int(np.count_nonzero(np.logical_and(room_mask, valid_mask))),
        "room_mask_valid_ratio": float(
            np.count_nonzero(np.logical_and(room_mask, valid_mask)) / max(np.count_nonzero(room_mask), 1)
        ),
        "room_validity": room_valid_stats,
        "ap_position_m": antenna.get("position_m"),
    }

    visualization_path = _save_radiomap_png(
        sionna_run_id,
        sionna_result["radiomap_dbm"],
        scene_plan=scene_plan,
        antenna=antenna,
        bounds=bounds,
    )
    valid_mask_path = _save_valid_mask_png(sionna_run_id, valid_mask)
    geometry_overlay_path = _save_geometry_overlay_png(
        sionna_run_id,
        scene_plan=scene_plan,
        antenna=antenna,
        bounds=bounds,
        width=arr.shape[1],
        height=arr.shape[0],
    )
    geometry_debug_path = _save_geometry_debug_json(sionna_run_id, geometry_debug_payload)
    runtime_result_path = _save_runtime_result_json(sionna_run_id, sionna_result)
    metrics = {
        "mode": "sionna_rt_runtime",
        "run_type": run_type,
        "floor_id": floor_id,
        "rssi_summary": sionna_result["rss_dbm"],
        "coverage_summary": sionna_result["coverage_summary"],
        "valid_cell_count": sionna_result.get("valid_cell_count"),
        "invalid_cell_count": sionna_result.get("invalid_cell_count"),
        "valid_ratio": sionna_result.get("valid_ratio"),
    }
    artifacts = {
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
    if visualization_path is not None:
        artifacts["visualization_path"] = visualization_path
    if runtime_result_path is not None:
        artifacts["runtime_result_path"] = runtime_result_path
    if valid_mask_path is not None:
        artifacts["valid_mask_path"] = valid_mask_path
    if geometry_overlay_path is not None:
        artifacts["geometry_overlay_path"] = geometry_overlay_path
    if geometry_debug_path is not None:
        artifacts["geometry_debug_path"] = geometry_debug_path
    artifacts["geometry_debug"] = geometry_debug_payload

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
