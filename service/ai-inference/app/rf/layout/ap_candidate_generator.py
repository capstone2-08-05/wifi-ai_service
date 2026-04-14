from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from app.rf.models.rf_models import Point2D, Room, Scene


@dataclass
class ApCandidate:
    candidate_id: str
    room_id: str
    x_m: float
    y_m: float
    z_m: float
    candidate_type: str
    score: float
    reasons: list[str]


def point_in_polygon(point: Point2D, polygon: tuple[Point2D, ...]) -> bool:
    x = point.x
    y = point.y
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i].x, polygon[i].y
        xj, yj = polygon[j].x, polygon[j].y
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_to_segment_distance(p: Point2D, a: Point2D, b: Point2D) -> float:
    ax, ay = a.x, a.y
    bx, by = b.x, b.y
    px, py = p.x, p.y

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay

    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        return math.dist((px, py), (ax, ay))

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab_len_sq))
    closest_x = ax + t * abx
    closest_y = ay + t * aby
    return math.dist((px, py), (closest_x, closest_y))


def distance_to_walls(scene: Scene, point: Point2D) -> float:
    min_dist = float("inf")
    for wall in scene.walls:
        dist = point_to_segment_distance(point, wall.start, wall.end)
        min_dist = min(min_dist, dist)
    return min_dist


def get_room_centroid(room: Room) -> Point2D:
    if room.centroid is not None:
        return room.centroid
    xs = [p.x for p in room.polygon]
    ys = [p.y for p in room.polygon]
    return Point2D(sum(xs) / len(xs), sum(ys) / len(ys))


def _polygon_bbox_aspect_ratio(polygon: tuple[Point2D, ...]) -> float:
    xs = [p.x for p in polygon]
    ys = [p.y for p in polygon]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w <= 1e-9 or h <= 1e-9:
        return 1.0
    return max(w / h, h / w)


def _corridor_span_points(room: Room) -> list[Point2D]:
    """Along the long side of the axis-aligned bbox, sample 1/3 and 2/3."""
    xs = [p.x for p in room.polygon]
    ys = [p.y for p in room.polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    w = max_x - min_x
    h = max_y - min_y
    if w >= h:
        return [
            Point2D(min_x + w / 3.0, cy),
            Point2D(min_x + 2.0 * w / 3.0, cy),
        ]
    return [
        Point2D(cx, min_y + h / 3.0),
        Point2D(cx, min_y + 2.0 * h / 3.0),
    ]


def score_room_candidate(scene: Scene, room: Room, point: Point2D) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    area = room.area_m2 or 0.0
    if area >= 20:
        score += 3.0
        reasons.append("large_room")
    elif area >= 10:
        score += 2.0
        reasons.append("medium_room")
    else:
        score += 1.0
        reasons.append("small_room")

    if room.space_type == "meeting_room":
        score += 2.0
        reasons.append("meeting_room")
    elif room.space_type == "corridor":
        score += 1.0
        reasons.append("corridor")

    wall_dist = distance_to_walls(scene, point)
    if wall_dist >= 1.0:
        score += 2.0
        reasons.append("safe_from_wall")
    elif wall_dist >= 0.5:
        score += 1.0
        reasons.append("acceptable_wall_clearance")
    else:
        score -= 5.0
        reasons.append("too_close_to_wall")

    return score, reasons


def _distance_xy(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _dedupe_min_spacing(
    candidates: list[ApCandidate], min_m: float = 1.5
) -> list[ApCandidate]:
    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
    kept: list[ApCandidate] = []
    for c in ordered:
        p = Point2D(c.x_m, c.y_m)
        if any(_distance_xy(p, Point2D(k.x_m, k.y_m)) < min_m for k in kept):
            continue
        kept.append(c)
    return kept


def generate_candidates(
    scene: Scene, mount_height_m: float = 2.5, min_wall_clearance_m: float = 0.5
) -> list[ApCandidate]:
    raw: list[tuple[str, str, Point2D, str]] = []
    cand_idx = 0

    for room in scene.rooms:
        centroid = get_room_centroid(room)
        if point_in_polygon(centroid, room.polygon):
            cand_idx += 1
            raw.append(
                (f"cand_{cand_idx:03d}", room.room_id, centroid, "room_centroid")
            )

        aspect = _polygon_bbox_aspect_ratio(room.polygon)
        if room.space_type == "corridor" or aspect >= 2.5:
            for p in _corridor_span_points(room):
                if not point_in_polygon(p, room.polygon):
                    continue
                cand_idx += 1
                raw.append(
                    (f"cand_{cand_idx:03d}", room.room_id, p, "corridor_span")
                )

    built: list[ApCandidate] = []
    for cid, room_id, point, ctype in raw:
        wall_dist = distance_to_walls(scene, point)
        if wall_dist < min_wall_clearance_m:
            continue
        room = next(r for r in scene.rooms if r.room_id == room_id)
        score, reasons = score_room_candidate(scene, room, point)
        if score < 0:
            continue
        built.append(
            ApCandidate(
                candidate_id=cid,
                room_id=room_id,
                x_m=point.x,
                y_m=point.y,
                z_m=mount_height_m,
                candidate_type=ctype,
                score=round(score, 3),
                reasons=reasons,
            )
        )

    deduped = _dedupe_min_spacing(built, min_m=1.5)
    return rank_candidates(deduped)


def rank_candidates(candidates: Iterable[ApCandidate]) -> list[ApCandidate]:
    return sorted(candidates, key=lambda c: c.score, reverse=True)
