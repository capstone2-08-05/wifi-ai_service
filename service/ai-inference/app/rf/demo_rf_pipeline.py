"""End-to-end 데모: scene → AP 후보 → layout → baseline 시뮬 → 산출물·영속 저장."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ap_candidate_generator import generate_candidates
from ap_layout_builder import ap_candidates_to_json_rows, candidates_to_ap_layout
from baseline_rf_simulator import (
    BaselineRfSimulator,
    load_json,
    print_run_summary,
    save_outputs,
)
from rf_models import Scene, SimulationConfig
from rf_persistence import JsonPersistenceStore


def _config_for_scene(config_path: Path, scene: Scene) -> SimulationConfig:
    data = load_json(config_path)
    data["scene_version_id"] = scene.scene_version_id
    return SimulationConfig.from_dict(data)


def _matplotlib_available() -> bool:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RF pipeline demo: candidates → layout → baseline → outputs + persistence."
    )
    p.add_argument(
        "--scene",
        type=Path,
        default=_ROOT / "sample" / "rf_scene_input.json",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=_ROOT / "sample" / "sim_config.json",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="후보 중 상위 K개로 ApLayout 구성",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=_ROOT / "sample" / "output" / "pipeline_demo",
        help="heatmap, npy, run_manifest.json 저장 폴더",
    )
    p.add_argument(
        "--skip-heatmap",
        action="store_true",
        help="matplotlib 없거나 CI일 때 PNG 생략 (npy/manifest는 저장)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    print("=== 1) Scene 로드 ===")
    scene = Scene.from_dict(load_json(args.scene))
    print(f"  scene_version_id={scene.scene_version_id}, rooms={len(scene.rooms)}, walls={len(scene.walls)}")

    print("\n=== 2) AP 후보 생성 ===")
    candidates = generate_candidates(scene)
    if not candidates:
        print("  후보가 없습니다. 씬에 유효한 room이 있는지 확인하세요.")
        sys.exit(1)
    for c in candidates:
        print(f"  {c}")

    print("\n=== 3) 상위 후보로 ApLayout ===")
    k = max(1, min(args.top_k, len(candidates)))
    picked = candidates[:k]
    layout = candidates_to_ap_layout(
        scene_version_id=scene.scene_version_id,
        layout_name="pipeline_topk",
        layout_type=f"heuristic_top{k}",
        candidates=picked,
    )
    print(json.dumps(layout.to_dict(), ensure_ascii=False, indent=2))

    print("\n=== 4) Baseline 시뮬레이션 ===")
    config = _config_for_scene(args.config, scene)
    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()

    print("\n=== 5) heatmap / manifest / npy 저장 ===")
    out_dir = args.output_dir
    skip_heatmap = args.skip_heatmap or not _matplotlib_available()
    if skip_heatmap and not args.skip_heatmap:
        print("  (matplotlib 미설치: heatmap PNG 생략, pip install matplotlib 권장)")
    manifest = save_outputs(
        scene=scene,
        ap_layout=layout,
        config=config,
        result=result,
        output_dir=out_dir,
        skip_heatmap=skip_heatmap,
    )
    manifest_path = out_dir / "run_manifest.json"
    print(f"  output_dir     : {out_dir.resolve()}")
    print(f"  run_manifest   : {manifest_path.resolve()}")
    if "heatmap_png" in manifest["artifacts"]:
        print(f"  heatmap        : {(out_dir / manifest['artifacts']['heatmap_png']).resolve()}")
    else:
        print("  heatmap        : (skipped)")

    print("\n=== 6) Persistence (JSON files) ===")
    persist_root = out_dir / "persistence"
    store = JsonPersistenceStore(persist_root)
    floor_id = scene.floor_id or "unknown_floor"
    rf_run = store.create_rf_run(
        scene_version_id=scene.scene_version_id,
        floor_id=floor_id,
        run_type="pipeline_demo",
        engine_name="baseline",
        engine_version="baseline-0.1",
        project_id=None,
        job_id=None,
        ap_candidates_json=ap_candidates_to_json_rows(candidates),
        sim_config_json={
            "grid_resolution_m": config.grid_resolution_m,
            "path_loss_constant_db": config.path_loss_constant_db,
            "path_loss_exponent": config.path_loss_exponent,
            "include_exterior_walls": config.include_exterior_walls,
            "output_dir_name": str(out_dir.name),
        },
        output_root=str(out_dir.resolve()),
    )
    placements_json = [
        {
            "ap_id": ap.ap_id,
            "ap_name": ap.ap_name,
            "x_m": ap.position.x,
            "y_m": ap.position.y,
            "z_m": ap.z_m,
            "tx_power_dbm": ap.tx_power_dbm,
            "frequency_ghz": ap.frequency_ghz,
        }
        for ap in layout.aps
    ]
    store.save_ap_layout(
        rf_run_id=rf_run.id,
        layout_name=layout.layout_name,
        layout_type=layout.layout_type,
        placements_json=placements_json,
    )
    store.finish_rf_run(
        rf_run_id=rf_run.id,
        status="succeeded",
        metrics_json=manifest["metrics"],
    )
    store.save_maps_from_manifest(
        rf_run_id=rf_run.id,
        manifest=manifest,
        output_dir=out_dir,
    )
    print(f"  persistence dir: {persist_root.resolve()}")
    print(f"  rf_run id      : {rf_run.id}")

    print()
    print("=== 결과 요약 ===")
    print_run_summary(scene=scene, ap_layout=layout, config=config, result=result)
    print()
    print("저장된 주요 파일:")
    print(f"  - {manifest_path}")
    print(f"  - {persist_root / 'rf_runs.json'}")
    print(f"  - {persist_root / 'ap_layouts.json'}")
    print(f"  - {persist_root / 'rf_maps.json'}")


if __name__ == "__main__":
    main()
