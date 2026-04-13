"""objects[] LOS 장애물 손실 (Baseline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.rf.fixtures.golden_fixtures import GOLDEN_CONFIG, GOLDEN_LAYOUT
from app.rf.models.rf_models import ApLayout, Scene, SimulationConfig
from app.rf.rules.object_obstacle_rules import (
    los_intersects_object_footprint,
    resolve_object_loss_db,
    segment_intersects_aabb,
)
from app.rf.simulation.baseline_rf_simulator import BaselineRfSimulator

_RF_ROOT = Path(__file__).resolve().parent.parent

np = pytest.importorskip("numpy")


def test_segment_intersects_aabb_diagonal() -> None:
    assert segment_intersects_aabb(0.0, 0.0, 4.0, 4.0, 1.0, 3.0, 1.0, 3.0)
    assert not segment_intersects_aabb(0.0, 0.0, 0.5, 0.5, 2.0, 3.0, 2.0, 3.0)


def test_resolve_loss_priority_attenuation_db() -> None:
    assert resolve_object_loss_db({"attenuation_db": 9.0, "type": "furniture_light"}) == 9.0


def test_los_hits_desk_footprint() -> None:
    obj = {
        "footprint_m": {"min_x": 2.0, "max_x": 4.0, "min_y": 1.5, "max_y": 2.5},
        "obstacle_class": "furniture_heavy",
    }
    assert los_intersects_object_footprint(0.5, 2.0, 5.5, 2.0, obj)


def test_scene_with_objects_lowers_rssi_along_los() -> None:
    """같은 AP·그리드에서 책상이 LOS 를 가리면 obstacle loss 로 RSSI 가 낮아진다."""
    base_scene = {
        "units": "m",
        "sourceType": "test",
        "scene_version_id": "golden_tiny_v1",
        "floor_id": "f1",
        "walls": [],
        "openings": [],
        "rooms": [
            {
                "id": "r1",
                "version_id": "golden_tiny_v1",
                "room_name": "R",
                "space_type": "room",
                "polygon_geom": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0], [0.0, 0.0]]
                    ],
                },
                "centroid_geom": {"type": "Point", "coordinates": [2.0, 2.0]},
                "area_m2": 16.0,
            }
        ],
        "objects": [],
    }
    scene_with_desk = {**base_scene, "objects": [
        {
            "id": "desk",
            "type": "furniture_heavy",
            "footprint_m": {"min_x": 1.0, "max_x": 2.0, "min_y": 1.5, "max_y": 2.5},
            "attenuation_db": 8.0,
        }
    ]}

    s0 = Scene.from_dict(base_scene)
    s1 = Scene.from_dict(scene_with_desk)
    layout = ApLayout.from_dict(GOLDEN_LAYOUT)
    cfg = SimulationConfig.from_dict(GOLDEN_CONFIG)

    r0 = BaselineRfSimulator(scene=s0, ap_layout=layout, config=cfg).run()
    r1 = BaselineRfSimulator(scene=s1, ap_layout=layout, config=cfg).run()

    # AP (2,2), 격자 해상도 1 → 인덱스 (3,2) 는 대략 (3,2) 로 책상(1~2, 1.5~2.5)과 LOS
    assert r1.strongest_rssi_map[2, 3] < r0.strongest_rssi_map[2, 3]


def test_sample_scene_with_objects_example_loads() -> None:
    import json

    path = _RF_ROOT / "sample" / "scene_with_objects_example.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    Scene.from_dict(raw)
