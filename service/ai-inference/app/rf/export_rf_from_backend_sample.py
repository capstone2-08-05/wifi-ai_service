"""
백엔드 scene graph DTO 샘플 → RF canonical JSON 생성 및 Scene 검증.

  python export_rf_from_backend_sample.py

입력: sample/backend_scene_graph_example.json, sample/backend_material_id_map.json
출력: sample/rf_scene_from_backend.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_RF = Path(__file__).resolve().parent
if str(_RF) not in sys.path:
    sys.path.insert(0, str(_RF))

from rf_models import Scene  # noqa: E402
from scene_to_rf_adapter import scene_graph_to_rf_scene_dict  # noqa: E402


def main() -> None:
    sample = _RF / "sample"
    backend = json.loads((sample / "backend_scene_graph_example.json").read_text(encoding="utf-8"))
    mat_map = json.loads((sample / "backend_material_id_map.json").read_text(encoding="utf-8"))

    out = scene_graph_to_rf_scene_dict(
        backend,
        material_id_to_profile_key=mat_map,
    )
    Scene.from_dict(out)
    (sample / "rf_scene_from_backend.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {sample / 'rf_scene_from_backend.json'} (Scene.from_dict OK)")


if __name__ == "__main__":
    main()
