from __future__ import annotations

import json
import sys
from pathlib import Path

_RF_ROOT = Path(__file__).resolve().parent.parent
if str(_RF_ROOT) not in sys.path:
    sys.path.insert(0, str(_RF_ROOT))

from app.rf.models.rf_models import ApLayout, Scene, SchemaValidationError, SimulationConfig

BASE_DIR = Path(__file__).resolve().parent
CASES_DIR = BASE_DIR / "rf_cases"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _assert_expected_counts(scene: Scene, layout: ApLayout, expected: dict) -> None:
    if "expected_wall_count" in expected:
        assert len(scene.walls) == expected["expected_wall_count"], (
            f"wall count {len(scene.walls)} != {expected['expected_wall_count']}"
        )
    if "expected_opening_count" in expected:
        assert len(scene.openings) == expected["expected_opening_count"], (
            f"opening count {len(scene.openings)} != {expected['expected_opening_count']}"
        )
    if "expected_room_count" in expected:
        assert len(scene.rooms) == expected["expected_room_count"], (
            f"room count {len(scene.rooms)} != {expected['expected_room_count']}"
        )
    if "expected_ap_count" in expected:
        assert len(layout.aps) == expected["expected_ap_count"], (
            f"ap count {len(layout.aps)} != {expected['expected_ap_count']}"
        )


def run_case(case_dir: Path) -> tuple[bool, str]:
    scene_data = _load_json(case_dir / "rf_scene_input.json")
    layout_data = _load_json(case_dir / "ap_layout_input.json")
    config_data = _load_json(case_dir / "sim_config.json")
    expected = _load_json(case_dir / "expected.json")

    should_pass = bool(expected["should_pass"])

    try:
        scene = Scene.from_dict(scene_data)
        layout = ApLayout.from_dict(layout_data)
        config = SimulationConfig.from_dict(config_data)

        if scene.scene_version_id != layout.scene_version_id:
            raise SchemaValidationError(
                "scene_version_id mismatch between scene and layout"
            )
        if scene.scene_version_id != config.scene_version_id:
            raise SchemaValidationError(
                "scene_version_id mismatch between scene and config"
            )

        wall_ids = {w.wall_id for w in scene.walls}
        for opening in scene.openings:
            if opening.wall_id not in wall_ids:
                raise SchemaValidationError(
                    f"opening {opening.opening_id} refers to missing wall_id={opening.wall_id}"
                )

        min_x, max_x, min_y, max_y = scene.bounds()
        for ap in layout.aps:
            if not (
                min_x <= ap.position.x <= max_x and min_y <= ap.position.y <= max_y
            ):
                raise SchemaValidationError(
                    f"ap {ap.ap_id} out of bounds: ({ap.position.x}, {ap.position.y})"
                )

        if should_pass:
            _assert_expected_counts(scene, layout, expected)
            return True, "PASS"
        return False, "Expected failure but passed"

    except (SchemaValidationError, ValueError) as e:
        if should_pass:
            return False, f"Expected pass but failed: {e}"
        return True, f"EXPECTED FAIL: {e}"
    except Exception as e:
        if should_pass:
            return False, f"Expected pass but failed: {e}"
        return True, f"EXPECTED FAIL: {e}"


def main() -> None:
    case_dirs = sorted(p for p in CASES_DIR.iterdir() if p.is_dir())
    total = len(case_dirs)
    passed = 0

    print("=== RF Schema Case Test ===")

    for case_dir in case_dirs:
        ok, msg = run_case(case_dir)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case_dir.name} -> {msg}")
        if ok:
            passed += 1

    print()
    print(f"Result: {passed}/{total} passed")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
