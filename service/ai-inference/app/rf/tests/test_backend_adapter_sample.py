"""백엔드 DTO 샘플 → adapter → Scene 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rf.conversion.scene_to_rf_adapter import scene_schema_to_rf_scene_dict
from app.rf.dto.backend_scene import SceneSchema
from app.rf.models.rf_models import Scene

_RF_ROOT = Path(__file__).resolve().parent.parent


def test_backend_sample_roundtrip_to_scene() -> None:
    sample = _RF_ROOT / "sample"
    backend = json.loads((sample / "backend_scene_graph_example.json").read_text(encoding="utf-8"))
    scene_dto = SceneSchema.model_validate(backend)
    out = scene_schema_to_rf_scene_dict(scene_dto)
    scene = Scene.from_dict(out)
    assert scene.scene_version_id == "sv_demo_backend_v1"
    assert len(scene.walls) == 5
    assert len(scene.openings) == 1
