"""Print heuristic AP candidates for the sample RF scene (run from repo: python demo_ap_candidates.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ap_candidate_generator import generate_candidates
from rf_models import Scene


def main() -> None:
    scene_path = _ROOT / "sample" / "rf_scene_input.json"
    with scene_path.open("r", encoding="utf-8") as f:
        scene_data = json.load(f)
    scene = Scene.from_dict(scene_data)
    candidates = generate_candidates(scene)
    print("=== AP Candidates ===")
    for c in candidates:
        print(c)


if __name__ == "__main__":
    main()
