"""
동일 golden 씬·AP 기준으로 baseline 요약과 Sionna RadioMap 요약을 한 JSON/MD로 낸다.

  python compare_baseline_vs_sionna.py
  python compare_baseline_vs_sionna.py --skip-sionna

Sionna 미설치·LLVM/CUDA 오류 시 자동으로 `sionna.status` = error 로 기록한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_RF = Path(__file__).resolve().parent
if str(_RF) not in sys.path:
    sys.path.insert(0, str(_RF))

from baseline_rf_simulator import BaselineRfSimulator  # noqa: E402
from golden_fixtures import GOLDEN_CONFIG, GOLDEN_LAYOUT, GOLDEN_SCENE  # noqa: E402
from rf_models import ApLayout, Scene, SimulationConfig  # noqa: E402
from sionna_poc.sionna_rt_poc import to_jsonable  # noqa: E402


def _baseline_block() -> dict:
    scene = Scene.from_dict(GOLDEN_SCENE)
    layout = ApLayout.from_dict(GOLDEN_LAYOUT)
    config = SimulationConfig.from_dict(GOLDEN_CONFIG)
    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()
    rssi = result.strongest_rssi_map
    return {
        "status": "ok",
        "model": "baseline_rf_simulator",
        "scene_version_id": scene.scene_version_id,
        "layout_name": layout.layout_name,
        "note": "Golden: 벽 없음, 2D 그리드. Sionna PoC는 3D 메시(바닥+벽) — 물리 모델이 다름.",
        "grid_shape": list(rssi.shape),
        "metrics": result.metrics,
        "rssi_dbm": {
            "min": float(np.min(rssi)),
            "max": float(np.max(rssi)),
            "mean": float(np.mean(rssi)),
        },
        "center_cell_rssi_dbm": float(rssi[rssi.shape[0] // 2, rssi.shape[1] // 2]),
    }


def _sionna_block(
    *,
    mesh_dir: Path,
    cell_size_m: float,
    samples_per_tx: int,
    max_depth: int,
    measurement_z_m: float,
    seed: int,
) -> dict:
    try:
        from sionna_poc.sionna_rt_poc import run_sionna_radiomap
    except Exception as e:
        return {"status": "error", "phase": "import_sionna_poc", "message": str(e)}

    try:
        _, summary = run_sionna_radiomap(
            mesh_dir=mesh_dir,
            cell_size_m=cell_size_m,
            samples_per_tx=samples_per_tx,
            max_depth=max_depth,
            measurement_z_m=measurement_z_m,
            seed=seed,
        )
        return {"status": "ok", **summary}
    except Exception as e:
        return {
            "status": "error",
            "phase": "run_sionna_radiomap",
            "message": str(e),
            "hint": "SIONNA_RUNBOOK.md 의 LLVM/CUDA/venv 절차 확인",
        }


def _interpretation_one_liner(baseline: dict, sionna: dict) -> str:
    if sionna.get("status") != "ok":
        return (
            "Sionna 측이 아직 실행되지 않았거나 오류라 수치 비교는 불가; "
            "baseline만으로 RF 파이프라인은 동작함을 시연할 수 있다."
        )
    return (
        "Baseline은 경로손실+벽손실(2D) 추정이고 Sionna는 3D 레이트레이싱 RSS로 "
        "같은 AP 위치라도 맵 값이 다르다; PoC 목적은 ‘동일 입력 축에서 두 엔진이 모두 산출된다’는 점이다."
    )


def _write_md(path: Path, report: dict) -> None:
    b = report["baseline"]
    s = report["sionna"]
    line = report["interpretation_one_liner"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if s.get("status") == "ok":
        rows = f"""| 항목 | Baseline | Sionna RSS (dBm) |
|------|----------|------------------|
| mean | {b['rssi_dbm']['mean']:.3f} | {s.get('rss_dbm', {}).get('mean', 'n/a')} |
| min | {b['rssi_dbm']['min']:.3f} | {s.get('rss_dbm', {}).get('min', 'n/a')} |
| max | {b['rssi_dbm']['max']:.3f} | {s.get('rss_dbm', {}).get('max', 'n/a')} |
"""
    else:
        rows = f"""| 항목 | Baseline | Sionna |
|------|----------|--------|
| mean (dBm) | {b['rssi_dbm']['mean']:.3f} | (실패: `{s.get('message', '')[:80]}`) |
| min | {b['rssi_dbm']['min']:.3f} | — |
| max | {b['rssi_dbm']['max']:.3f} | — |

Sionna 열은 `sionna.status != ok` 이면 비움. `SIONNA_RUNBOOK.md` 참고.
"""

    body = f"""# Baseline vs Sionna (golden)

- 생성 시각: {report.get("generated_at_utc", "")}
- 조건: 동일 `golden_fixtures` AP (2,2) m, z=2.5 m, 5 GHz (baseline은 벽 없음 / Sionna는 메시 방)

## 한 줄 해석

{line}

## 지표

{rows}

## 상세

- Baseline `metrics`: JSON `baseline.metrics`
- Sionna: JSON `sionna` 블록
"""
    path.write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sionna", action="store_true")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=_RF / "sample" / "output" / "baseline_vs_sionna_summary.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=_RF / "sample" / "output" / "baseline_vs_sionna_summary.md",
    )
    parser.add_argument("--mesh-dir", type=Path, default=_RF / "sionna_poc" / "meshes")
    parser.add_argument("--cell-size-m", type=float, default=1.0)
    parser.add_argument("--samples-per-tx", type=int, default=300_000)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--measurement-z-m", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    baseline = _baseline_block()
    if args.skip_sionna:
        sionna = {"status": "skipped", "message": "--skip-sionna"}
    else:
        sionna = _sionna_block(
            mesh_dir=args.mesh_dir,
            cell_size_m=args.cell_size_m,
            samples_per_tx=args.samples_per_tx,
            max_depth=args.max_depth,
            measurement_z_m=args.measurement_z_m,
            seed=args.seed,
        )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "sionna": sionna,
        "interpretation_one_liner": _interpretation_one_liner(baseline, sionna),
    }
    safe_report = to_jsonable(report)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(safe_report, f, ensure_ascii=False, indent=2)
    _write_md(args.out_md, safe_report)
    print(f"Wrote {args.out_json}")
    print(f"Wrote {args.out_md}")


if __name__ == "__main__":
    main()
