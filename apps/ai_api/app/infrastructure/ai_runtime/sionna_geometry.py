"""Sionna 결과 후처리에 필요한 기하 헬퍼 (좌표 변환, polygon, 방 마스크/통계)."""

from __future__ import annotations

from typing import Any

import numpy as np


def to_grid_xy(x: float, y: float, bounds: dict[str, Any], width: int, height: int) -> tuple[float, float]:
    min_x = float(bounds.get("min_x", 0.0))
    max_x = float(bounds.get("max_x", 1.0))
    min_y = float(bounds.get("min_y", 0.0))
    max_y = float(bounds.get("max_y", 1.0))
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    gx = (float(x) - min_x) / span_x * max(width - 1, 1)
    gy = (float(y) - min_y) / span_y * max(height - 1, 1)
    return gx, gy


def to_world_xy(gx: float, gy: float, bounds: dict[str, Any], width: int, height: int) -> tuple[float, float]:
    min_x = float(bounds.get("min_x", 0.0))
    max_x = float(bounds.get("max_x", 1.0))
    min_y = float(bounds.get("min_y", 0.0))
    max_y = float(bounds.get("max_y", 1.0))
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    wx = min_x + float(gx) / max(width, 1) * span_x
    wy = min_y + float(gy) / max(height, 1) * span_y
    return wx, wy


def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
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


def _polygon_from_room(room: dict[str, Any]) -> list[tuple[float, float]]:
    points = room.get("points")
    if not isinstance(points, list) or len(points) < 3:
        return []
    polygon: list[tuple[float, float]] = []
    for p in points:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                polygon.append((float(p[0]), float(p[1])))
            except Exception:
                continue
    return polygon if len(polygon) >= 3 else []


def _polygon_mask(polygon: list[tuple[float, float]], bounds: dict[str, Any], width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for gy in range(height):
        for gx in range(width):
            wx, wy = to_world_xy(gx + 0.5, gy + 0.5, bounds, width, height)
            if point_in_polygon(wx, wy, polygon):
                mask[gy, gx] = True
    return mask


def build_room_mask(scene_plan: dict[str, Any], bounds: dict[str, Any], width: int, height: int) -> np.ndarray:
    room_mask = np.zeros((height, width), dtype=bool)
    for room in scene_plan.get("rooms", []):
        polygon = _polygon_from_room(room)
        if not polygon:
            continue
        room_mask |= _polygon_mask(polygon, bounds, width, height)
    return room_mask


def room_validity_stats(
    scene_plan: dict[str, Any],
    bounds: dict[str, Any],
    valid_mask: np.ndarray,
) -> dict[str, Any]:
    height, width = valid_mask.shape
    room_stats: list[dict[str, Any]] = []
    total_room_cells = 0
    total_valid_in_rooms = 0
    for room in scene_plan.get("rooms", []):
        polygon = _polygon_from_room(room)
        if not polygon:
            continue
        mask = _polygon_mask(polygon, bounds, width, height)
        room_cells = int(np.count_nonzero(mask))
        valid_cells = int(np.count_nonzero(np.logical_and(mask, valid_mask)))
        total_room_cells += room_cells
        total_valid_in_rooms += valid_cells
        room_stats.append(
            {
                "room_id": str(room.get("id", "room")),
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


__all__ = [
    "to_grid_xy",
    "to_world_xy",
    "point_in_polygon",
    "build_room_mask",
    "room_validity_stats",
]
