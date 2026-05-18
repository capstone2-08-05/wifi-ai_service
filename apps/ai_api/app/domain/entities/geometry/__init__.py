"""Geometry domain — 도면 객체의 위치/형상 표현.

전파 상호작용 특성은 [radio.RadioMaterial]로 분리되어 있으며,
각 객체는 `material_id`로 RadioMaterial을 참조한다.
"""

from app.domain.entities.geometry.wall import WallObject
from app.domain.entities.geometry.opening import OpeningKind, OpeningObject
from app.domain.entities.geometry.room import RoomObject
from app.domain.entities.geometry.furniture import FurnitureObject
from app.domain.entities.geometry.scene import FloorScene, SceneBounds

__all__ = [
    "WallObject",
    "OpeningKind",
    "OpeningObject",
    "RoomObject",
    "FurnitureObject",
    "FloorScene",
    "SceneBounds",
]
