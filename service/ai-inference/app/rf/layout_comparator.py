"""동일 scene·config에서 여러 ApLayout의 baseline 지표를 비교한다 (캡스톤 시연용)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ap_candidate_generator import generate_candidates
from ap_layout_builder import candidates_to_ap_layout
from baseline_rf_simulator import BaselineRfSimulator, load_json
from rf_models import ApLayout, Scene, SimulationConfig


def _config_for_scene(config_path: Path, scene: Scene) -> SimulationConfig:
    data = load_json(config_path)
    data["scene_version_id"] = scene.scene_version_id
    return SimulationConfig.from_dict(data)


def _row_from_metrics(layout_label: str, metrics: dict[str, Any]) -> dict[str, Any]:
    rs = metrics["rssi_summary"]
    cs = metrics["coverage_summary"]
    return {
        "layout_label": layout_label,
        "mean_dbm": rs["mean_dbm"],
        "min_dbm": rs["min_dbm"],
        "coverage_ratio_ge_neg67_dbm": cs["fraction_rssi_ge_neg67_dbm"],
        "coverage_ratio_ge_neg70_dbm": cs["fraction_rssi_ge_neg70_dbm"],
        "dead_zone_ratio_lt_neg75_dbm": cs["dead_zone_fraction_lt_neg75_dbm"],
    }


def build_comparison_layouts(
    scene: Scene, candidates: list
) -> list[tuple[str, ApLayout]]:
    """manual 후보는 호출 측에서 넣고, 여기서는 후보 기반 레이아웃만 생성."""
    out: list[tuple[str, ApLayout]] = []
    if not candidates:
        return out
    out.append(
        (
            "candidate_top1",
            candidates_to_ap_layout(
                scene_version_id=scene.scene_version_id,
                layout_name="compare_candidate_top1",
                layout_type="heuristic_top1",
                candidates=candidates[:1],
            ),
        )
    )
    n2 = min(2, len(candidates))
    out.append(
        (
            "candidate_top2",
            candidates_to_ap_layout(
                scene_version_id=scene.scene_version_id,
                layout_name="compare_candidate_top2",
                layout_type="heuristic_top2",
                candidates=candidates[:n2],
            ),
        )
    )
    return out


def run_layout_comparison(
    *,
    scene_path: Path,
    config_path: Path,
    manual_layout_path: Path,
    summary_json_path: Path | None = None,
) -> dict[str, Any]:
    scene = Scene.from_dict(load_json(scene_path))
    config = _config_for_scene(config_path, scene)
    manual_layout = ApLayout.from_dict(load_json(manual_layout_path))
    candidates = generate_candidates(scene)

    layouts: list[tuple[str, ApLayout]] = [
        ("manual", manual_layout),
    ]
    layouts.extend(build_comparison_layouts(scene, candidates))

    rows: list[dict[str, Any]] = []
    per_layout: list[dict[str, Any]] = []

    for label, layout in layouts:
        sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
        result = sim.run()
        rows.append(_row_from_metrics(label, result.metrics))
        per_layout.append(
            {
                "layout_label": label,
                "layout_name": layout.layout_name,
                "ap_count": len(layout.aps),
                "metrics": result.metrics,
            }
        )

    summary: dict[str, Any] = {
        "scene_version_id": scene.scene_version_id,
        "scene_path": str(scene_path.resolve()),
        "config_path": str(config_path.resolve()),
        "grid_resolution_m": config.grid_resolution_m,
        "comparison_rows": rows,
        "per_layout": per_layout,
    }

    if summary_json_path is not None:
        summary_json_path.parent.mkdir(parents=True, exist_ok=True)
        summary_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return summary


def print_comparison_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        "layout",
        "mean_dbm",
        "min_dbm",
        "cov>=-67",
        "cov>=-70",
        "dead<-75",
    ]
    print(" | ".join(headers))
    print("-" * (len(" | ".join(headers)) + 5))
    for r in rows:
        line = " | ".join(
            [
                str(r["layout_label"])[:20],
                f"{r['mean_dbm']:.2f}",
                f"{r['min_dbm']:.2f}",
                f"{r['coverage_ratio_ge_neg67_dbm']:.3f}",
                f"{r['coverage_ratio_ge_neg70_dbm']:.3f}",
                f"{r['dead_zone_ratio_lt_neg75_dbm']:.3f}",
            ]
        )
        print(line)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare AP layouts on the same scene (baseline).")
    p.add_argument(
        "--scene",
        type=Path,
        default=_ROOT / "sample" / "rf_scene_input.json",
        help="RF scene JSON",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=_ROOT / "sample" / "sim_config.json",
        help="sim_config.json (scene_version_id는 scene에 맞게 덮어씀)",
    )
    p.add_argument(
        "--manual-layout",
        type=Path,
        default=_ROOT / "sample" / "ap_layout_input.json",
        help="수동 배치 ApLayout JSON",
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=_ROOT / "sample" / "output" / "layout_comparison_summary.json",
        help="비교 결과 JSON 경로",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_layout_comparison(
        scene_path=args.scene,
        config_path=args.config,
        manual_layout_path=args.manual_layout,
        summary_json_path=args.output_json,
    )
    print()
    print("=== Layout comparison (baseline) ===")
    print_comparison_table(summary["comparison_rows"])
    print()
    print(f"Saved: {args.output_json.resolve()}")


if __name__ == "__main__":
    main()
