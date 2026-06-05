"""Sionna 결과의 시각화/JSON 아티팩트 생성·디스크 저장.

## Thread safety

`matplotlib.pyplot` 사용 X — pyplot 은 전역 figure registry + "current figure" 포인터를
관리하는 stateful module 이라 FastAPI sync route 가 thread pool 에서 동시 호출되면
race condition (figure mix-up, 메모리 누수) 가능.

→ OO API (`matplotlib.figure.Figure` + 명시적 `FigureCanvasAgg`) 만 사용. Figure 객체는
   함수 local scope 라 thread 간 격리, GC 도 자동 (pyplot 의 close() 불필요).

`matplotlib.use("Agg")` 도 필요 없음 — `FigureCanvasAgg` 를 직접 박으므로.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from app.infrastructure.ai_runtime.sionna_geometry import to_grid_xy
from app.infrastructure.settings import OUTPUT_DIR

INVALID_DBM_THRESHOLD = -200.0
RADIOMAP_CMAP = "jet"


def resolve_radiomap_color_limits(
    radiomap_dbm: list[list[float]] | np.ndarray,
    visualization_cfg: dict[str, Any] | None = None,
) -> tuple[float, float]:
    """이 run 의 heatmap auto color scale (p5-p95) — sionna_gateway 등 외부에서 사용.

    invalid 셀 (값 <= INVALID_DBM_THRESHOLD) 은 제외하고 percentile 계산.
    valid 값이 비었거나 spread 가 너무 좁으면 fallback (cfg 의 -90/-30 등) 사용.
    """
    arr = np.asarray(radiomap_dbm, dtype=float)
    valid = arr[arr > INVALID_DBM_THRESHOLD]
    return _resolve_auto_color_limits(valid, visualization_cfg)


def _resolve_auto_color_limits(
    valid_values: np.ndarray,
    visualization_cfg: dict[str, Any] | None = None,
) -> tuple[float, float]:
    cfg = visualization_cfg or {}
    fb_lo = float(cfg.get("heatmap_fallback_vmin_dbm", -90.0))
    fb_hi = float(cfg.get("heatmap_fallback_vmax_dbm", -30.0))
    if valid_values.size == 0:
        return (fb_lo, fb_hi)
    p_lo = float(cfg.get("heatmap_clip_percentile_lo", 5.0))
    p_hi = float(cfg.get("heatmap_clip_percentile_hi", 95.0))
    min_span = float(cfg.get("heatmap_min_span_db", 8.0))
    lo, hi = np.percentile(valid_values, [p_lo, p_hi])
    if not np.isfinite(lo) or not np.isfinite(hi):
        return (fb_lo, fb_hi)
    if float(hi - lo) < min_span:
        mid = float(np.mean(valid_values))
        half = min_span / 2.0
        return (mid - half, mid + half)
    return (float(lo), float(hi))


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


def _new_figure(figsize: tuple[float, float], dpi: int = 100) -> Figure:
    """Thread-safe figure 생성 — Agg canvas 명시적으로 연결, pyplot 안 거침.

    pyplot 의 전역 figure registry/current-figure 포인터를 안 건드리므로 thread 간 race
    없음. canvas 가 fig.canvas 로 접근 가능 (matplotlib 이 자동 연결).
    """
    fig = Figure(figsize=figsize, dpi=dpi)
    FigureCanvasAgg(fig)  # canvas 를 fig 에 attach (생성자가 fig.canvas 로 등록)
    return fig


def save_radiomap_png(
    sionna_run_id: str,
    radiomap_dbm: list[list[float]],
    *,
    scene_plan: dict[str, Any],
    antenna: dict[str, Any],
    bounds: dict[str, Any],
    visualization_cfg: dict[str, Any] | None = None,
) -> str | None:
    """Sionna RadioMap → 2 개의 PNG 동시 저장.

      1) radiomap_heatmap.png : **clean overlay (chrome 없음)** + image 규약 y (top=row0).
         프론트 캔버스의 `<image>` 가 floor 좌표에 1:1 정렬해서 깔려야 하므로 이게 1차.

      2) radiomap_heatmap_annotated.png : 디버그/사람 보기용 (제목/축/colorbar/legend 포함).
         physics 규약(origin=lower) + scene overlay (벽/AP/문 등). 검증용 — 캔버스 X.

    이전엔 (2) 형식만 저장해서 chrome 도 캔버스에 깔리고 Y축이 뒤집혀 보였음 (#bugfix).
    """
    try:
        arr = np.asarray(radiomap_dbm, dtype=float)
        valid_values = arr[arr > INVALID_DBM_THRESHOLD]
        vmin, vmax = _resolve_auto_color_limits(valid_values, visualization_cfg)
        masked = np.ma.masked_where(arr <= INVALID_DBM_THRESHOLD, arr)
        cmap = mpl.colormaps[RADIOMAP_CMAP].copy()
        cmap.set_bad(color="#5a5a5a", alpha=0.0)  # invalid 셀은 투명 — 캔버스 배경 노출

        out_dir = _output_dir(sionna_run_id)

        # (1) Clean overlay — 캔버스 정렬용.
        # default origin (= 'upper'): PNG row 0 = data row 0 → SVG y=minY (top) 에 그려져
        # walls/AP 의 image 규약 (y=0 이 top) 와 정확히 일치.
        overlay_path = out_dir / "radiomap_heatmap.png"
        h, w = arr.shape
        # 데이터 한 셀당 픽셀 1:1 보존 (interpolation 은 SVG/브라우저가 알아서 늘림).
        fig_overlay = _new_figure(figsize=(w / 100.0, h / 100.0), dpi=100)
        ax_overlay = fig_overlay.subplots()
        ax_overlay.imshow(
            masked,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            interpolation="nearest",
        )
        ax_overlay.axis("off")
        fig_overlay.subplots_adjust(left=0, right=1, top=1, bottom=0)
        fig_overlay.savefig(
            overlay_path, dpi=100, bbox_inches="tight", pad_inches=0, transparent=True
        )

        # (2) Annotated debug — 사람 보기용 (현재 캔버스에는 안 깔림).
        annotated_path = out_dir / "radiomap_heatmap_annotated.png"
        fig_ann = _new_figure(figsize=(7.2, 5.4))
        ax_ann = fig_ann.subplots()
        cmap_ann = mpl.colormaps[RADIOMAP_CMAP].copy()
        cmap_ann.set_bad(color="#5a5a5a", alpha=1.0)
        im = ax_ann.imshow(
            masked,
            origin="lower",
            cmap=cmap_ann,
            vmin=vmin,
            vmax=vmax,
            interpolation="bicubic",
        )
        _draw_scene_overlay(
            ax_ann,
            scene_plan=scene_plan,
            antenna=antenna,
            bounds=bounds,
            width=arr.shape[1],
            height=arr.shape[0],
        )
        ax_ann.set_title("Sionna RT RadioMap (debug)")
        ax_ann.set_xlabel("X grid")
        ax_ann.set_ylabel("Y grid")
        cbar = fig_ann.colorbar(im, ax=ax_ann)
        cbar.set_label(f"RSS (dBm), auto scale p5-p95 [{vmin:.1f}, {vmax:.1f}]")
        fig_ann.text(
            0.02, 0.01,
            "Gray = not simulated / invalid cell",
            fontsize=8, color="#444444",
        )
        fig_ann.tight_layout()
        fig_ann.savefig(annotated_path, dpi=150)

        return str(overlay_path.resolve())
    except Exception:
        return None


def save_valid_mask_png(sionna_run_id: str, valid_mask: np.ndarray) -> str | None:
    try:
        out_path = _output_dir(sionna_run_id) / "valid_mask.png"
        fig = _new_figure(figsize=(7.2, 5.4))
        ax = fig.subplots()
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
        fig.tight_layout()
        fig.savefig(out_path, dpi=140)
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
        fig = _new_figure(figsize=(7.2, 5.4))
        ax = fig.subplots()
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
        fig.tight_layout()
        fig.savefig(out_path, dpi=140)
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
    "resolve_radiomap_color_limits",
    "save_radiomap_png",
    "save_valid_mask_png",
    "save_geometry_overlay_png",
    "save_geometry_debug_json",
    "save_runtime_result_json",
]
