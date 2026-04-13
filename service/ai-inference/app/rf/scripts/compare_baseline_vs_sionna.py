"""
동일 golden 씬·AP 기준으로 baseline 요약과 Sionna RadioMap 요약을 한 JSON/MD로 낸다.

  python app/rf/scripts/compare_baseline_vs_sionna.py
  python app/rf/scripts/compare_baseline_vs_sionna.py --skip-sionna
  python app/rf/scripts/compare_baseline_vs_sionna.py --frozen-sionna sample/output/sionna_poc_frozen.json

발표 고정본: preview(Baseline) vs precise(Sionna) 역할 차이 중심. 수치 우열이 아님.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_AI = Path(__file__).resolve().parents[3]
_RF = Path(__file__).resolve().parents[1]
for _p in (_AI, _RF):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.rf.fixtures.golden_fixtures import (  # noqa: E402
    GOLDEN_CONFIG,
    GOLDEN_LAYOUT,
    GOLDEN_SCENE,
)
from app.rf.models.rf_models import ApLayout, Scene, SimulationConfig  # noqa: E402
from app.rf.simulation.baseline_rf_simulator import BaselineRfSimulator  # noqa: E402
from app.rf.sionna_poc.sionna_rt_poc import to_jsonable  # noqa: E402

_SAMPLE = _RF / "sample"
_FROZEN_SIONNA_DEFAULT = _SAMPLE / "output" / "sionna_poc_frozen.json"


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
        "note": (
            "Baseline: 2D floorplan preview(빠른 반복). "
            "Sionna: 동일 입력 축의 내부 precise 검증(레이트레이싱; 서비스 UI 전면의 3D가 아님)."
        ),
        "grid_shape": list(rssi.shape),
        "metrics": result.metrics,
        "rssi_dbm": {
            "min": float(np.min(rssi)),
            "max": float(np.max(rssi)),
            "mean": float(np.mean(rssi)),
        },
        "center_cell_rssi_dbm": float(rssi[rssi.shape[0] // 2, rssi.shape[1] // 2]),
    }


def _complex_baseline_preview_block() -> dict:
    """Sionna PoC mesh와 별개인 복잡 씬 — Baseline preview 시연용만 (동일 Sionna 비교는 미적용)."""
    scene_path = _SAMPLE / "rf_scene_input_complex.json"
    layout_path = _SAMPLE / "ap_layout_input_complex.json"
    cfg_path = _SAMPLE / "sim_config_complex.json"
    if not all(p.exists() for p in (scene_path, layout_path, cfg_path)):
        return {
            "status": "skipped",
            "message": "complex sample files missing",
        }
    scene = Scene.from_dict(json.loads(scene_path.read_text(encoding="utf-8")))
    layout = ApLayout.from_dict(json.loads(layout_path.read_text(encoding="utf-8")))
    config = SimulationConfig.from_dict(json.loads(cfg_path.read_text(encoding="utf-8")))
    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()
    rssi = result.strongest_rssi_map
    return {
        "status": "ok",
        "role": "baseline_preview_only",
        "scene_version_id": scene.scene_version_id,
        "layout_name": layout.layout_name,
        "note": (
            "PoC Sionna는 golden 4×4 m 단순 메시 고정. "
            "이 씬은 벽·개구·방이 많은 Baseline heatmap 데모용이며 Sionna와의 1:1 수치 비교는 하지 않는다."
        ),
        "grid_shape": list(rssi.shape),
        "rssi_dbm": {
            "min": float(np.min(rssi)),
            "max": float(np.max(rssi)),
            "mean": float(np.mean(rssi)),
        },
        "metrics_summary": {
            "mean_dbm": float(result.metrics["rssi_summary"]["mean_dbm"]),
            "min_dbm": float(result.metrics["rssi_summary"]["min_dbm"]),
            "max_dbm": float(result.metrics["rssi_summary"]["max_dbm"]),
        },
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
            "hint": "RUNBOOK.md 의 Sionna/LLVM 절차 확인",
        }


def _load_frozen_sionna(path: Path) -> dict | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "sionna" in raw and isinstance(raw["sionna"], dict):
        return raw["sionna"]
    return raw


def _save_frozen_sionna(path: Path, sionna: dict) -> None:
    if sionna.get("status") != "ok":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    skip = frozenset({"status", "source"})
    snap = {k: v for k, v in sionna.items() if k not in skip}
    snap["status"] = "ok"
    snap["snapshot_version"] = snap.get("snapshot_version", "auto_saved")
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def _presentation_block(
    baseline: dict,
    sionna: dict,
    complex_preview: dict,
) -> dict:
    """발표용: 역할 표 + 슬라이드용 수치(반올림). 우열이 아니라 preview vs precise."""
    rows_roles = [
        {
            "axis": "사용자에게 보이는 주 화면",
            "baseline_preview": "2D floorplan + heatmap 중심, 빠른 반복",
            "sionna_precise": "동일 제품 축에서 내부 검증(레이트레이싱·3D 기하)",
        },
        {
            "axis": "목적",
            "baseline_preview": "배치·재질·개구·가구 배치 변화를 즉시 시각화",
            "sionna_precise": "동일 입력 축에서 정밀 RSS/경로 특성 참고",
        },
        {
            "axis": "수치 일치",
            "baseline_preview": "preview용 단순 모델",
            "sionna_precise": "1:1 일치는 목표 아님 (역할이 다름)",
        },
    ]
    golden_table = None
    if baseline.get("status") == "ok":
        golden_table = {
            "scene": "golden_fixtures (5×5 m 그리드, 벽 없음)",
            "baseline_mean_dbm_rounded": round(baseline["rssi_dbm"]["mean"], 2),
            "baseline_min_dbm_rounded": round(baseline["rssi_dbm"]["min"], 2),
            "baseline_max_dbm_rounded": round(baseline["rssi_dbm"]["max"], 2),
        }
        if sionna.get("status") == "ok" and "rss_dbm" in sionna:
            rss = sionna["rss_dbm"]
            golden_table["sionna_mean_dbm_rounded"] = round(float(rss["mean"]), 2)
            golden_table["sionna_min_dbm_rounded"] = round(float(rss["min"]), 2)
            golden_table["sionna_max_dbm_rounded"] = round(float(rss["max"]), 2)
        else:
            golden_table["sionna_mean_dbm_rounded"] = None
            golden_table["sionna_note"] = "Sionna 미실행 시 표에서 생략"

    complex_note = None
    if complex_preview.get("status") == "ok":
        complex_note = (
            "복잡 씬(`rf_scene_input_complex.json`)은 Baseline preview 데모용. "
            "Sionna PoC 메시는 단순 방 고정이라 **이 씬과의 동시 비교는 하지 않음**."
        )

    return {
        "title": "Preview vs Precise (발표 고정 문구)",
        "tagline": "Baseline = 빠른 미리보기 · Sionna = 정밀 검증 · 같은 입력 축에서 둘 다 동작",
        "not_a_contest": (
            "수치 우열이 아니라 역할 차이: 제품 UX는 preview, 내부/연구는 precise로 같은 DTO·씬 축을 공유한다."
        ),
        "role_comparison_rows": rows_roles,
        "golden_comparison_rounded_dbm": golden_table,
        "complex_scene_decision": complex_note,
        "slide_table_markdown": _slide_table_markdown(baseline, sionna),
    }


def _slide_table_markdown(baseline: dict, sionna: dict) -> str:
    if baseline.get("status") != "ok":
        return ""
    b = baseline["rssi_dbm"]
    if sionna.get("status") == "ok" and "rss_dbm" in sionna:
        s = sionna["rss_dbm"]
        return (
            "| 구분 | Baseline (preview) | Sionna (precise) |\n"
            "|------|-------------------|------------------|\n"
            "| 역할 | 빠른 2D heatmap | 레이트레이싱 RadioMap |\n"
            f"| RSSI mean (dBm) | {round(b['mean'], 2)} | {round(float(s['mean']), 2)} |\n"
            f"| RSSI min (dBm) | {round(b['min'], 2)} | {round(float(s['min']), 2)} |\n"
            f"| RSSI max (dBm) | {round(b['max'], 2)} | {round(float(s['max']), 2)} |\n"
        )
    return (
        "| 구분 | Baseline (preview) | Sionna (precise) |\n"
        "|------|-------------------|------------------|\n"
        "| 역할 | 빠른 2D heatmap | (실행 시 레이트레이싱 RadioMap) |\n"
        f"| RSSI mean (dBm) | {round(b['mean'], 2)} | — |\n"
    )


def _interpretation_one_liner(baseline: dict, sionna: dict) -> str:
    if sionna.get("status") != "ok":
        return (
            "Sionna 측이 아직 실행되지 않았거나 오류라 수치 비교는 불가; "
            "Baseline preview 파이프라인은 동작함을 시연할 수 있다. "
            "정밀 축은 `sionna_poc_frozen.json` 스냅샷 또는 재실행으로 보완."
        )
    return (
        "같은 입력 축(golden)에서 Baseline은 빠른 preview, Sionna는 precise 검증이다. "
        "수치 1:1 일치는 목표가 아니며, 제품은 2D heatmap 중심이다."
    )


def _write_md(path: Path, report: dict) -> None:
    b = report["baseline"]
    s = report["sionna"]
    pres = report.get("presentation") or {}
    line = report["interpretation_one_liner"]
    path.parent.mkdir(parents=True, exist_ok=True)

    if s.get("status") == "ok" and "rss_dbm" in s:
        rss = s["rss_dbm"]
        rows = f"""| 항목 | Baseline (preview) | Sionna (precise) |
|------|-------------------|------------------|
| mean (dBm) | {b['rssi_dbm']['mean']:.3f} | {rss.get('mean')} |
| min (dBm) | {b['rssi_dbm']['min']:.3f} | {rss.get('min')} |
| max (dBm) | {b['rssi_dbm']['max']:.3f} | {rss.get('max')} |
"""
    else:
        rows = f"""| 항목 | Baseline | Sionna |
|------|----------|--------|
| mean (dBm) | {b['rssi_dbm']['mean']:.3f} | (실패 또는 미실행: `{str(s.get('message', ''))[:120]}`) |

Sionna 열은 `sionna.status != ok` 이면 비움. `RUNBOOK.md` 또는 `--frozen-sionna` 참고.
"""

    slide = pres.get("slide_table_markdown") or ""
    tag = pres.get("tagline", "")
    not_contest = pres.get("not_a_contest", "")
    complex_decision = pres.get("complex_scene_decision") or ""

    role_md = ""
    for row in pres.get("role_comparison_rows") or []:
        role_md += f"- **{row['axis']}**: preview — {row['baseline_preview']} / precise — {row['sionna_precise']}\n"

    srf = report.get("sionna_resolved_from", "?")
    body = f"""# Baseline vs Sionna — 발표용 최종본 (golden)

- 생성 시각(UTC): {report.get("generated_at_utc", "")}
- 조건: 동일 `golden_fixtures` — AP (2, 2) m, z = 2.5 m, 5 GHz, 그리드 해상도 1 m
- Sionna 수치 출처: **{srf}** (`live_run` = 이번 RadioMap 재실행, `frozen_snapshot` = `sionna_poc_frozen.json` 에 저장된 PoC 성공값)

## 한 줄

**{tag}**

{not_contest}

## 해석 (한 줄)

{line}

## 역할 비교 (preview vs precise)

{role_md}

## 복잡 씬에 대한 판단

{complex_decision or "(없음)"}

## 지표 표 (동일 golden 입력 축)

{rows}

## 슬라이드용 표 (복사용)

{slide}

## 상세

- 전체 JSON: `baseline_vs_sionna_summary.json` 의 `baseline`, `sionna`, `presentation`, `complex_baseline_preview`
- Sionna PoC 스냅샷: `sionna_poc_frozen.json` (라이브 실행 성공 시 갱신; 실패 시 발표용으로 동일 파일 fallback)

## 발표 캡처 참고 (Baseline heatmap 예시)

- 단일 AP: `sample/output/presentation_final/01_manual_single_ap/strongest_rssi_heatmap.png`
- 2 AP 후보: `sample/output/presentation_final/02_auto_candidate_2ap/strongest_rssi_heatmap.png`
- 복잡 씬 Baseline: `sample/output/pipeline_complex_demo/strongest_rssi_heatmap.png`

(Sionna는 RadioMap 수치·내부 검증 위주; 슬라이드에는 위 **역할 표**와 golden 수치 표를 권장.)
"""
    path.write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-sionna", action="store_true")
    parser.add_argument(
        "--frozen-sionna",
        type=Path,
        default=None,
        help="Sionna 실패 시 이 JSON의 sionna 블록을 합성 (기본: sample/output/sionna_poc_frozen.json)",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=_SAMPLE / "output" / "baseline_vs_sionna_summary.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=_SAMPLE / "output" / "baseline_vs_sionna_summary.md",
    )
    parser.add_argument("--mesh-dir", type=Path, default=_RF / "sionna_poc" / "meshes")
    parser.add_argument("--cell-size-m", type=float, default=1.0)
    parser.add_argument("--samples-per-tx", type=int, default=300_000)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--measurement-z-m", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    baseline = _baseline_block()
    complex_preview = _complex_baseline_preview_block()

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
        if sionna.get("status") == "ok":
            _save_frozen_sionna(_FROZEN_SIONNA_DEFAULT, sionna)
        else:
            frozen_path = args.frozen_sionna or _FROZEN_SIONNA_DEFAULT
            loaded = _load_frozen_sionna(frozen_path)
            if loaded is not None:
                sionna = {**loaded, "status": "ok"}
                sionna["source"] = f"frozen_file:{frozen_path.resolve()}"

    presentation = _presentation_block(baseline, sionna, complex_preview)

    sionna_from = (
        "frozen_snapshot"
        if isinstance(sionna.get("source"), str) and "frozen_file" in sionna["source"]
        else "live_run"
    )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "document_version": "presentation_final_1",
        "sionna_resolved_from": sionna_from,
        "baseline": baseline,
        "sionna": sionna,
        "complex_baseline_preview": complex_preview,
        "presentation": presentation,
        "interpretation_one_liner": _interpretation_one_liner(baseline, sionna),
    }
    safe_report = to_jsonable(report)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    with args.out_json.open("w", encoding="utf-8") as f:
        json.dump(safe_report, f, ensure_ascii=False, indent=2)
    _write_md(args.out_md, safe_report)

    slide_path = args.out_md.parent / "baseline_vs_sionna_slide_table.md"
    slide_path.write_text(
        "# 슬라이드용 표 (Baseline vs Sionna)\n\n"
        + (presentation.get("slide_table_markdown") or "")
        + "\n\n---\n\n"
        + (presentation.get("tagline", ""))
        + "\n\n"
        + (presentation.get("not_a_contest") or ""),
        encoding="utf-8",
    )
    print(f"Wrote {args.out_json}")
    print(f"Wrote {args.out_md}")
    print(f"Wrote {slide_path}")


if __name__ == "__main__":
    main()
