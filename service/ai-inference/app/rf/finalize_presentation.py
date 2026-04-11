"""발표용 산출물을 한 디렉터리에 고정 생성한다 (같은 씬·config, 배치만 다름).

출력: sample/output/presentation_final/
  - 01_manual_single_ap/run_manifest.json, strongest_rssi_heatmap.png, *.npy
  - 02_auto_candidate_2ap/run_manifest.json, strongest_rssi_heatmap.png, *.npy
  - layout_comparison_summary.json / .md

재현: python finalize_presentation.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ap_candidate_generator import generate_candidates
from ap_layout_builder import candidates_to_ap_layout
from baseline_rf_simulator import BaselineRfSimulator, load_json, save_outputs
from layout_comparator import run_layout_comparison
from rf_models import ApLayout, Scene, SimulationConfig

# 발표 확정본: 복잡 씬 + 동일 sim_config (path loss 등 동일해야 비교가 의미 있음)
SCENE = _ROOT / "sample" / "rf_scene_input_complex.json"
CONFIG = _ROOT / "sample" / "sim_config_complex.json"
MANUAL_LAYOUT = _ROOT / "sample" / "ap_layout_input_complex.json"

OUT = _ROOT / "sample" / "output" / "presentation_final"
DIR_MANUAL = OUT / "01_manual_single_ap"
DIR_2AP = OUT / "02_auto_candidate_2ap"


def _config_for_scene(config_path: Path, scene: Scene) -> SimulationConfig:
    data = load_json(config_path)
    data["scene_version_id"] = scene.scene_version_id
    return SimulationConfig.from_dict(data)


def _matplotlib_ok() -> bool:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_readme() -> None:
    body = f"""# 발표용 RF 산출물 (고정 스냅샷)

동일 씬·동일 `sim_config_complex.json`에서 **AP 배치만** 달리한 결과입니다.

| 항목 | 경로 |
|------|------|
| 단일 AP 히트맵 | `{DIR_MANUAL.relative_to(OUT)}/strongest_rssi_heatmap.png` |
| 단일 AP manifest | `{DIR_MANUAL.relative_to(OUT)}/run_manifest.json` |
| 후보 기반 2AP 히트맵 | `{DIR_2AP.relative_to(OUT)}/strongest_rssi_heatmap.png` |
| 2AP manifest | `{DIR_2AP.relative_to(OUT)}/run_manifest.json` |
| 레이아웃 비교표 (JSON) | `layout_comparison_summary.json` |
| 레이아웃 비교표 (MD) | `layout_comparison_summary.md` |

## 재생성 (저장소 루트 기준)

```bash
cd service/ai-inference/app/rf
python finalize_presentation.py
```

matplotlib이 없으면 PNG는 생략되고 npy·manifest·비교 JSON/MD는 생성됩니다.

상위 안내: `app/rf/PRESENTATION_LOCKED.md`
"""
    (OUT / "README.md").write_text(body, encoding="utf-8")


def main() -> None:
    skip_h = not _matplotlib_ok()
    if skip_h:
        print("matplotlib 없음: heatmap PNG는 생략합니다. (pip install matplotlib 권장)")

    scene = Scene.from_dict(load_json(SCENE))
    config = _config_for_scene(CONFIG, scene)

    # --- 1) 수동 단일 AP ---
    layout_manual = ApLayout.from_dict(load_json(MANUAL_LAYOUT))
    sim1 = BaselineRfSimulator(scene, layout_manual, config)
    r1 = sim1.run()
    save_outputs(
        scene, layout_manual, config, r1, DIR_MANUAL, skip_heatmap=skip_h
    )
    print(f"[ok] {DIR_MANUAL.relative_to(_ROOT)}  layout={layout_manual.layout_name}")

    # --- 2) 자동 후보 상위 2개 → 2AP ---
    cands = generate_candidates(scene)
    if len(cands) < 2:
        raise SystemExit("후보가 2개 미만입니다. 씬/후보 생성 로직을 확인하세요.")
    layout_2ap = candidates_to_ap_layout(
        scene_version_id=scene.scene_version_id,
        layout_name="presentation_auto_2ap",
        layout_type="heuristic_top2",
        candidates=cands[:2],
    )
    sim2 = BaselineRfSimulator(scene, layout_2ap, config)
    r2 = sim2.run()
    save_outputs(scene, layout_2ap, config, r2, DIR_2AP, skip_heatmap=skip_h)
    print(f"[ok] {DIR_2AP.relative_to(_ROOT)}  layout={layout_2ap.layout_name}")

    # --- 3) 비교표 (동일 씬·config·manual layout 파일) ---
    summary = run_layout_comparison(
        scene_path=SCENE,
        config_path=CONFIG,
        manual_layout_path=MANUAL_LAYOUT,
        summary_json_path=OUT / "layout_comparison_summary.json",
        summary_md_path=OUT / "layout_comparison_summary.md",
    )
    print(f"[ok] {OUT.relative_to(_ROOT)}/layout_comparison_summary.*")
    interp = summary.get("interpretation_ko", "")
    print("interpretation:", (interp[:200] + "…") if len(interp) > 200 else interp)

    _write_readme()

    meta = {
        "scene": str(SCENE.resolve()),
        "config": str(CONFIG.resolve()),
        "manual_layout": str(MANUAL_LAYOUT.resolve()),
        "input_files_sha256": {
            "rf_scene_input_complex.json": _sha256_file(SCENE),
            "sim_config_complex.json": _sha256_file(CONFIG),
            "ap_layout_input_complex.json": _sha256_file(MANUAL_LAYOUT),
        },
        "heatmap_png_generated": not skip_h,
        "outputs": {
            "manual_single_ap_dir": str(DIR_MANUAL.resolve()),
            "auto_2ap_dir": str(DIR_2AP.resolve()),
            "comparison_json": str((OUT / "layout_comparison_summary.json").resolve()),
            "comparison_md": str((OUT / "layout_comparison_summary.md").resolve()),
        },
        "candidate_top2_ap_ids": [ap.ap_id for ap in layout_2ap.aps],
    }
    (OUT / "snapshot_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[ok] {OUT.relative_to(_ROOT)}/README.md, snapshot_meta.json")
    print("\n발표용 폴더:", OUT.resolve())


if __name__ == "__main__":
    main()
