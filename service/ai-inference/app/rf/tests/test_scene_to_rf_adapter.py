"""scene_graph_to_rf_scene_dict → Scene.from_dict 스모크."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RF_ROOT = Path(__file__).resolve().parent.parent
if str(_RF_ROOT) not in sys.path:
    sys.path.insert(0, str(_RF_ROOT))

from rf_models import Scene  # noqa: E402
from scene_to_rf_adapter import scene_graph_to_rf_scene_dict  # noqa: E402


def test_complex_sample_roundtrips_through_adapter() -> None:
    path = _RF_ROOT / "sample" / "rf_scene_input_complex.json"
    graph = json.loads(path.read_text(encoding="utf-8"))
    out = scene_graph_to_rf_scene_dict(graph)
    scene = Scene.from_dict(out)
    assert scene.scene_version_id == "scene_complex_v1"
    assert len(scene.walls) == 6
    assert len(scene.openings) == 3
    assert len(scene.rooms) == 3


def test_material_id_resolution() -> None:
    graph = {
        "scene_version_id": "v1",
        "sourceType": "test",
        "walls": [
            {
                "id": "w1",
                "x1": 0.0,
                "y1": 0.0,
                "x2": 1.0,
                "y2": 0.0,
                "thickness": 0.2,
                "height": 2.8,
                "role": "outer",
                "material_id": "m_conc",
            }
        ],
        "openings": [],
        "rooms": [
            {
                "id": "r1",
                "room_name": "R",
                "space_type": "room",
                "polygon_geom": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
                },
            }
        ],
        "objects": [],
    }
    out = scene_graph_to_rf_scene_dict(
        graph,
        material_id_to_profile_key={"m_conc": "concrete"},
    )
    scene = Scene.from_dict(out)
    assert scene.walls[0].material == "concrete"
