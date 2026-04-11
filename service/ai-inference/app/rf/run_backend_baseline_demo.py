"""
RF canonical 샘플(sample/rf_scene_from_backend.json)로 baseline 시뮬레이션 1회 실행.

  python run_backend_baseline_demo.py

출력: stdout에 metrics JSON (발표/로그용)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_RF = Path(__file__).resolve().parent
if str(_RF) not in sys.path:
    sys.path.insert(0, str(_RF))

from baseline_rf_simulator import BaselineRfSimulator  # noqa: E402
from rf_models import ApLayout, Scene, SimulationConfig  # noqa: E402


def main() -> None:
    sample = _RF / "sample"
    scene = Scene.from_dict(json.loads((sample / "rf_scene_from_backend.json").read_text(encoding="utf-8")))
    layout = ApLayout.from_dict(json.loads((sample / "ap_layout_backend_demo.json").read_text(encoding="utf-8")))
    config = SimulationConfig.from_dict(json.loads((sample / "simulation_config_backend_demo.json").read_text(encoding="utf-8")))

    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()
    payload = {
        "scene_version_id": scene.scene_version_id,
        "layout_name": layout.layout_name,
        "metrics": result.metrics,
        "grid_shape": list(result.strongest_rssi_map.shape),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
