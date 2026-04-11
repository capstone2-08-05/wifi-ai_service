"""백엔드 DTO 샘플 → adapter → Scene 검증."""

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


def test_backend_sample_roundtrip_to_scene() -> None:
    sample = _RF_ROOT / "sample"
    backend = json.loads((sample / "backend_scene_graph_example.json").read_text(encoding="utf-8"))
    mmap = json.loads((sample / "backend_material_id_map.json").read_text(encoding="utf-8"))
    out = scene_graph_to_rf_scene_dict(backend, material_id_to_profile_key=mmap)
    scene = Scene.from_dict(out)
    assert scene.scene_version_id == "sv_demo_backend_v1"
    assert len(scene.walls) == 5
    assert len(scene.openings) == 1
