"""Print heuristic AP candidates for the sample RF scene (run from repo: python demo_ap_candidates.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ap_candidate_generator import generate_candidates
from ap_layout_builder import candidates_to_ap_layout, save_ap_layout_json
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

    if candidates:
        top = candidates[: min(3, len(candidates))]
        layout = candidates_to_ap_layout(
            scene_version_id=scene.scene_version_id,
            layout_name="heuristic_top3",
            layout_type="from_candidates",
            candidates=top,
        )
        out_path = _ROOT / "sample" / "output" / "ap_layout_from_candidates.json"
        save_ap_layout_json(layout, out_path)
        print()
        print(f"=== Wrote ApLayout (top {len(top)}) -> {out_path}")


if __name__ == "__main__":
    main()
