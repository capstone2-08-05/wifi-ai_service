"""
백엔드 floorplan DTO 샘플 → RF canonical JSON 생성 및 Scene 검증.

  python export_rf_from_backend_sample.py

입력: sample/backend_scene_graph_example.json (`backend/app/schemas/floorplan.py` 계약)
출력: sample/rf_scene_from_backend.json

변환: ``SceneSchema.model_validate`` → ``scene_to_rf_adapter.scene_schema_to_rf_scene_dict``
(내부적으로 ``adapter_baseline_dto.scene_schema_to_baseline_rf_scene_dict``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_AI = Path(__file__).resolve().parents[2]
_RF = Path(__file__).resolve().parent
for _p in (_AI, _RF):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend_scene_dto import SceneSchema  # noqa: E402
from rf_models import Scene  # noqa: E402
from scene_to_rf_adapter import scene_schema_to_rf_scene_dict  # noqa: E402


def main() -> None:
    sample = _RF / "sample"
    raw = json.loads((sample / "backend_scene_graph_example.json").read_text(encoding="utf-8"))
    scene = SceneSchema.model_validate(raw)
    out = scene_schema_to_rf_scene_dict(scene)
    Scene.from_dict(out)
    (sample / "rf_scene_from_backend.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {sample / 'rf_scene_from_backend.json'} (Scene.from_dict OK)")


if __name__ == "__main__":
    main()
