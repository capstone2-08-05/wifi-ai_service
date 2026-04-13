"""
objects[] → Baseline 2D 장애물(가구·clutter) 추가 손실 규칙.

3D 메시 없음. `docs/OBJECTS_FURNITURE_SCHEMA.md`, `docs/BASELINE_OBJECTS_OBSTACLE_RULES.md` 참고.
"""

from __future__ import annotations

from typing import Any, Mapping

EPS = 1e-9

# obstacle_class / type 기본 추가 손실 [dB] (preview, 튜닝 가능)
DEFAULT_OBSTACLE_CLASS_DB: dict[str, float] = {
    "furniture_heavy": 6.0,
    "furniture_light": 2.5,
    "storage": 3.5,
    "clutter": 1.5,
    "partition": 2.0,
    "appliance": 4.0,
    "unknown": 2.5,
}

# material 문자열(가구 재질 분류) → 장애물 강도 (벽 material enum과 별개)
DEFAULT_OBSTACLE_MATERIAL_DB: dict[str, float] = {
    "wood": 2.5,
    "metal": 5.0,
    "fabric": 2.0,
    "glass": 1.0,
    "plastic": 1.5,
    "unknown": 2.5,
}


def object_bbox_m(obj: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    """
    객체의 2D 축정렬 경계 (meter).

    우선순위: ``footprint_m`` | ``bbox_m`` (동일 형식 ``min_x,max_x,min_y,max_y``) → ``points`` 의 AABB.
    """
    fp = obj.get("footprint_m") or obj.get("bbox_m")
    if isinstance(fp, dict):
        try:
            return (
                float(fp["min_x"]),
                float(fp["max_x"]),
                float(fp["min_y"]),
                float(fp["max_y"]),
            )
        except (KeyError, TypeError, ValueError):
            pass
    pts = obj.get("points")
    if isinstance(pts, list) and len(pts) >= 1:
        xs: list[float] = []
        ys: list[float] = []
        for p in pts:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    xs.append(float(p[0]))
                    ys.append(float(p[1]))
                except (TypeError, ValueError):
                    continue
        if len(xs) >= 1 and len(ys) >= 1:
            return (min(xs), max(xs), min(ys), max(ys))
    return None


def _on_segment(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> bool:
    return (
        min(ax, bx) - EPS <= cx <= max(ax, bx) + EPS
        and min(ay, by) - EPS <= cy <= max(ay, by) + EPS
    )


def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def segments_intersect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
    eps: float = EPS,
) -> bool:
    """선분 (a,b) 와 (c,d) 교차·접촉."""
    d1 = _ccw(ax, ay, bx, by, cx, cy)
    d2 = _ccw(ax, ay, bx, by, dx, dy)
    d3 = _ccw(cx, cy, dx, dy, ax, ay)
    d4 = _ccw(cx, cy, dx, dy, bx, by)

    if (d1 * d2 < 0) and (d3 * d4 < 0):
        return True
    if abs(d1) < eps and _on_segment(ax, ay, bx, by, cx, cy):
        return True
    if abs(d2) < eps and _on_segment(ax, ay, bx, by, dx, dy):
        return True
    if abs(d3) < eps and _on_segment(cx, cy, dx, dy, ax, ay):
        return True
    if abs(d4) < eps and _on_segment(cx, cy, dx, dy, bx, by):
        return True
    return False


def segment_intersects_aabb(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
) -> bool:
    """선분 AP–Rx 가 축정렬 사각형과 교차하거나, 끝점이 내부에 있으면 True."""
    def inside(px: float, py: float) -> bool:
        return min_x <= px <= max_x and min_y <= py <= max_y

    if inside(ax, ay) or inside(bx, by):
        return True
    edges = (
        ((min_x, min_y), (max_x, min_y)),
        ((max_x, min_y), (max_x, max_y)),
        ((max_x, max_y), (min_x, max_y)),
        ((min_x, max_y), (min_x, min_y)),
    )
    for (x1, y1), (x2, y2) in edges:
        if segments_intersect(ax, ay, bx, by, x1, y1, x2, y2):
            return True
    return False


def resolve_object_loss_db(obj: Mapping[str, Any]) -> float:
    """
    객체 1개에 대한 추가 손실 [dB].

    우선순위: ``attenuation_db`` > ``obstacle_class`` > ``type`` > ``material``(가구) > 기본.
    """
    raw = obj.get("attenuation_db")
    if raw is not None:
        try:
            v = float(raw)
            return max(0.0, v)
        except (TypeError, ValueError):
            pass
    for key in ("obstacle_class", "type"):
        s = obj.get(key)
        if isinstance(s, str) and s.strip():
            k = s.strip().lower()
            if k in DEFAULT_OBSTACLE_CLASS_DB:
                return DEFAULT_OBSTACLE_CLASS_DB[k]
    mat = obj.get("material")
    if isinstance(mat, str) and mat.strip():
        k = mat.strip().lower()
        if k in DEFAULT_OBSTACLE_MATERIAL_DB:
            return DEFAULT_OBSTACLE_MATERIAL_DB[k]
    return DEFAULT_OBSTACLE_CLASS_DB["unknown"]


def los_intersects_object_footprint(
    ap_x: float,
    ap_y: float,
    rx_x: float,
    rx_y: float,
    obj: Mapping[str, Any],
) -> bool:
    """AP–수신 직선이 객체 2D footprint(AABB) 와 겹치는지."""
    bb = object_bbox_m(obj)
    if bb is None:
        return False
    mn_x, mx_x, mn_y, mx_y = bb
    return segment_intersects_aabb(ap_x, ap_y, rx_x, rx_y, mn_x, mx_x, mn_y, mx_y)
