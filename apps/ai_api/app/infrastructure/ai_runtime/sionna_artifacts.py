"""Sionna 결과의 시각화/JSON 아티팩트 생성·디스크 저장."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from app.infrastructure.ai_runtime.sionna_geometry import to_grid_xy
from app.infrastructure.settings import OUTPUT_DIR

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


def _opening_endpoints(opening: dict[str, Any], walls_by_id: dict[str, dict[str, Any]]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    wall = walls_by_id.get(str(opening.get("wall_id", "")))
    if wall is None:
        return None
    try:
        wx1, wy1 = float(wall["x1"]), float(wall["y1"])
        wx2, wy2 = float(wall["x2"]), float(wall["y2"])
        cx, cy = float(opening["center_xy"][0]), float(opening["center_xy"][1])
        half = float(opening["width_m"]) / 2.0
    except Exception:
        return None
    dx, dy = wx2 - wx1, wy2 - wy1
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 1e-9:
        return None
    ux, uy = dx / length, dy / length
    return ((cx - ux * half, cy - uy * half), (cx + ux * half, cy + uy * half))


def _polygon_centroid(polygon: list[Any]) -> tuple[float, float] | None:
    try:
        xs = [float(p[0]) for p in polygon]
        ys = [float(p[1]) for p in polygon]
    except Exception:
        return None
    if not xs:
        return None
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _draw_scene_overlay(
    ax: Any,
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    width: int,
    height: int,
) -> None:
    walls = scene_plan.get("walls", []) or []
    walls_by_id: dict[str, dict[str, Any]] = {str(w.get("id", "")): w for w in walls if isinstance(w, dict)}

    for wall in walls:
        try:
            x1, y1 = to_grid_xy(float(wall["x1"]), float(wall["y1"]), bounds, width, height)
            x2, y2 = to_grid_xy(float(wall["x2"]), float(wall["y2"]), bounds, width, height)
        except Exception:
            continue
        ax.plot([x1, x2], [y1, y2], color="white", linewidth=1.2, alpha=0.9)

    for opening in scene_plan.get("openings", []):
        endpoints = _opening_endpoints(opening, walls_by_id)
        if endpoints is None:
            continue
        (sx, sy), (ex, ey) = endpoints
        try:
            gx1, gy1 = to_grid_xy(sx, sy, bounds, width, height)
            gx2, gy2 = to_grid_xy(ex, ey, bounds, width, height)
        except Exception:
            continue
        ax.plot([gx1, gx2], [gy1, gy2], color="#35d4ff", linewidth=1.4, linestyle="--", alpha=0.95)

    for room in scene_plan.get("rooms", []):
        polygon = room.get("polygon_xy")
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        rid = str(room.get("id", "")).strip()
        if not rid:
            continue
        centroid = _polygon_centroid(polygon)
        if centroid is None:
            continue
        try:
            cx, cy = to_grid_xy(centroid[0], centroid[1], bounds, width, height)
        except Exception:
            continue
        ax.text(cx, cy, rid, color="white", fontsize=6, ha="center", va="center", alpha=0.9)

    for piece in scene_plan.get("furniture", []) or []:
        polygon = piece.get("polygon_xy")
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        try:
            grid_pts = [
                to_grid_xy(float(p[0]), float(p[1]), bounds, width, height)
                for p in polygon
                if len(p) >= 2
            ]
        except Exception:
            continue
        if len(grid_pts) < 3:
            continue
        # closed polygon outline
        gx = [p[0] for p in grid_pts] + [grid_pts[0][0]]
        gy = [p[1] for p in grid_pts] + [grid_pts[0][1]]
        ax.plot(gx, gy, color="#ffbf47", linewidth=1.0, linestyle=":", alpha=0.9)

    pos = antenna.get("position_m")
    if isinstance(pos, list) and len(pos) >= 2:
        try:
            tx, ty = to_grid_xy(float(pos[0]), float(pos[1]), bounds, width, height)
            ax.scatter([tx], [ty], marker="*", s=90, c="#00ffd0", edgecolors="black", linewidths=0.8, zorder=5)
        except Exception:
            pass

    legend_handles = [
        Line2D([0], [0], color="white", linewidth=1.2, label="Wall"),
        Line2D([0], [0], color="#35d4ff", linewidth=1.4, linestyle="--", label="Opening"),
        Line2D([0], [0], color="#ffbf47", linewidth=1.0, linestyle=":", label="Furniture"),
        Line2D([0], [0], marker="*", markersize=10, markerfacecolor="#00ffd0", markeredgecolor="black", linewidth=0, label="AP"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=7, framealpha=0.75)


def _output_dir(sionna_run_id: str) -> Path:
    out_dir = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_radiomap_png(
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
        out_path = _output_dir(sionna_run_id) / "radiomap_heatmap.png"
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
        return str(out_path.resolve())
    except Exception:
        return None


def save_valid_mask_png(sionna_run_id: str, valid_mask: np.ndarray) -> str | None:
    try:
        out_path = _output_dir(sionna_run_id) / "valid_mask.png"
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


def save_geometry_overlay_png(
    sionna_run_id: str,
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    width: int,
    height: int,
) -> str | None:
    try:
        out_path = _output_dir(sionna_run_id) / "geometry_overlay.png"
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


def save_geometry_debug_json(sionna_run_id: str, payload: dict[str, Any]) -> str | None:
    try:
        out_path = _output_dir(sionna_run_id) / "geometry_debug.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path.resolve())
    except Exception:
        return None


def save_runtime_result_json(sionna_run_id: str, runtime_result: dict[str, Any]) -> str | None:
    try:
        out_path = _output_dir(sionna_run_id) / "runtime_result.json"
        out_path.write_text(json.dumps(runtime_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path.resolve())
    except Exception:
        return None


__all__ = [
    "INVALID_DBM_THRESHOLD",
    "save_radiomap_png",
    "save_valid_mask_png",
    "save_geometry_overlay_png",
    "save_geometry_debug_json",
    "save_runtime_result_json",
]
