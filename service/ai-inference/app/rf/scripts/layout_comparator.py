"""동일 scene·config에서 manual / candidate_top1 / candidate_top2 레이아웃을 비교한다 (발표용)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_AI = Path(__file__).resolve().parents[3]
_RF = Path(__file__).resolve().parents[1]
for _p in (_AI, _RF):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.rf.layout.ap_candidate_generator import generate_candidates
from app.rf.layout.ap_layout_builder import candidates_to_ap_layout
from app.rf.models.rf_models import ApLayout, Scene, SimulationConfig
from app.rf.simulation.baseline_rf_simulator import BaselineRfSimulator, load_json

EXPERIMENT_PURPOSE_KO = (
    "동일한 실내 씬에서 AP 배치 전략만 바꿔 baseline RF 모델로 strongest RSSI를 비교한다. "
    "단일 수동 배치 대비 휴리스틱 후보(top-1, top-2)가 평균·최저 RSSI와 커버리지·데드존에 "
    "어떤 영향을 주는지 정량적으로 보여 주기 위한 실험이다."
)


def _config_for_scene(config_path: Path, scene: Scene) -> SimulationConfig:
    data = load_json(config_path)
    data["scene_version_id"] = scene.scene_version_id
    return SimulationConfig.from_dict(data)


def _serving_display(counts: dict[str, int]) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _row_from_metrics(layout_label: str, metrics: dict[str, Any]) -> dict[str, Any]:
    rs = metrics["rssi_summary"]
    cs = metrics["coverage_summary"]
    wl = metrics["wall_loss_summary"]
    sd = metrics["serving_ap_distribution"]["counts"]
    return {
        "layout_label": layout_label,
        "mean_dbm": rs["mean_dbm"],
        "min_dbm": rs["min_dbm"],
        "fraction_rssi_ge_neg67_dbm": cs["fraction_rssi_ge_neg67_dbm"],
        "fraction_rssi_ge_neg70_dbm": cs["fraction_rssi_ge_neg70_dbm"],
        "dead_zone_fraction_lt_neg75_dbm": cs["dead_zone_fraction_lt_neg75_dbm"],
        "wall_loss_mean_db": wl["mean_db"],
        "serving_ap_counts": dict(sd),
        "serving_ap_counts_display": _serving_display(sd),
    }


def _interpret_comparison(rows: list[dict[str, Any]]) -> str:
    by = {r["layout_label"]: r for r in rows}
    if "manual" not in by or "candidate_top2" not in by:
        return "manual·candidate_top2 비교 행이 없어 자동 해석을 생략합니다."
    m = by["manual"]
    t2 = by["candidate_top2"]
    t1 = by.get("candidate_top1")
    parts: list[str] = []
    dm = float(t2["mean_dbm"]) - float(m["mean_dbm"])
    dmin = float(t2["min_dbm"]) - float(m["min_dbm"])
    dead_m = float(m["dead_zone_fraction_lt_neg75_dbm"])
    dead_t2 = float(t2["dead_zone_fraction_lt_neg75_dbm"])
    d_dead = dead_m - dead_t2
    if dm >= 0.5:
        parts.append(f"후보 기반 2AP 배치에서 평균 RSSI가 단일 AP 대비 약 {dm:.2f} dB 개선되었다.")
    elif dm > 0:
        parts.append(f"평균 RSSI는 약 {dm:.2f} dB 소폭 개선되었다.")
    elif dm < -0.3:
        parts.append(f"평균 RSSI는 약 {-dm:.2f} dB 감소했다(후보·격자 설정에 따라 달라질 수 있음).")
    if dmin > 0.5:
        parts.append(f"최저 RSSI는 약 {dmin:.2f} dB 개선되어 약한 구간이 완화되었다.")
    if d_dead > 0.02:
        parts.append(
            f"데드존(RSSI < -75 dBm) 격자 비율은 약 {d_dead*100:.1f}%p 감소했다."
        )
    elif d_dead < -0.02:
        parts.append(
            f"데드존 비율은 약 {-d_dead*100:.1f}%p 증가했다."
        )
    elif dead_m > 0.001 and dead_t2 <= 0.0005:
        parts.append(
            "단일 AP에서는 일부 격자가 데드존이었으나, 2AP 배치에서는 데드존이 사라졌다."
        )
    wl_d = float(m["wall_loss_mean_db"]) - float(t2["wall_loss_mean_db"])
    if wl_d > 0.05:
        parts.append(
            "평균 벽 손실은 다중 AP·서빙 구역 분담으로 상대적으로 완화된 것으로 나타난다."
        )
    if t1 is not None:
        parts.append(
            f"top-1 대비 top-2는 평균 RSSI 차이 {float(t2['mean_dbm']) - float(t1['mean_dbm']):.2f} dB."
        )
    if not parts:
        return "세 레이아웃 간 수치 차이는 설정된 임계값 기준으로는 작다."
    return " ".join(parts)


def render_layout_comparison_markdown(summary: dict[str, Any]) -> str:
    purpose = summary.get("experiment_purpose_ko", EXPERIMENT_PURPOSE_KO)
    interp = summary.get("interpretation_ko", "")
    rows = summary["comparison_rows"]
    layouts_desc = [
        "- **manual**: 사용자(발표)가 고정한 단일 AP 배치",
        "- **candidate_top1**: 휴리스틱 후보 1위만 반영한 단일 AP",
        "- **candidate_top2**: 휴리스틱 상위 2개 후보를 반영한 2AP 배치",
    ]
    lines = [
        "# RF 레이아웃 비교 요약 (baseline)",
        "",
        "## 실험 목적",
        "",
        purpose,
        "",
        "## 비교한 layout",
        "",
        *layouts_desc,
        "",
        f"- scene: `{summary.get('scene_path', '')}`",
        f"- config: `{summary.get('config_path', '')}` (grid {summary.get('grid_resolution_m', '')} m)",
        "",
        "## 핵심 수치",
        "",
        "| layout | mean RSSI (dBm) | min RSSI (dBm) | ≥-67 | ≥-70 | dead<-75 | wall loss μ (dB) | serving (counts) |",
        "|--------|-----------------|----------------|------|------|----------|------------------|------------------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['layout_label']} | {r['mean_dbm']:.2f} | {r['min_dbm']:.2f} | "
            f"{r['fraction_rssi_ge_neg67_dbm']:.3f} | {r['fraction_rssi_ge_neg70_dbm']:.3f} | "
            f"{r['dead_zone_fraction_lt_neg75_dbm']:.3f} | {r['wall_loss_mean_db']:.3f} | "
            f"{r['serving_ap_counts_display']} |"
        )
    lines.extend(
        [
            "",
            "## 한 줄 해석",
            "",
            interp,
            "",
        ]
    )
    return "\n".join(lines)


def build_comparison_layouts(
    scene: Scene, candidates: list
) -> list[tuple[str, ApLayout]]:
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
    summary_md_path: Path | None = None,
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

    interpretation_ko = _interpret_comparison(rows)

    summary: dict[str, Any] = {
        "scene_version_id": scene.scene_version_id,
        "scene_path": str(scene_path.resolve()),
        "config_path": str(config_path.resolve()),
        "grid_resolution_m": config.grid_resolution_m,
        "experiment_purpose_ko": EXPERIMENT_PURPOSE_KO,
        "interpretation_ko": interpretation_ko,
        "comparison_rows": rows,
        "per_layout": per_layout,
    }

    if summary_json_path is not None:
        summary_json_path.parent.mkdir(parents=True, exist_ok=True)
        summary_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if summary_md_path is not None:
        summary_md_path.parent.mkdir(parents=True, exist_ok=True)
        summary_md_path.write_text(
            render_layout_comparison_markdown(summary),
            encoding="utf-8",
        )

    return summary


def print_comparison_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        "layout",
        "mean",
        "min",
        "≥-67",
        "≥-70",
        "dead",
        "wl_μ",
        "serving",
    ]
    print(" | ".join(headers))
    print("-" * 100)
    for r in rows:
        line = " | ".join(
            [
                str(r["layout_label"])[:16],
                f"{r['mean_dbm']:.2f}",
                f"{r['min_dbm']:.2f}",
                f"{r['fraction_rssi_ge_neg67_dbm']:.3f}",
                f"{r['fraction_rssi_ge_neg70_dbm']:.3f}",
                f"{r['dead_zone_fraction_lt_neg75_dbm']:.3f}",
                f"{r['wall_loss_mean_db']:.3f}",
                r["serving_ap_counts_display"][:32],
            ]
        )
        print(line)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare AP layouts on the same scene (baseline).")
    p.add_argument(
        "--scene",
        type=Path,
        default=_RF / "sample" / "rf_scene_input_complex.json",
        help="RF scene JSON (기본: 발표용 복잡 씬)",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=_RF / "sample" / "sim_config_complex.json",
        help="sim_config.json",
    )
    p.add_argument(
        "--manual-layout",
        type=Path,
        default=_RF / "sample" / "ap_layout_input_complex.json",
        help="수동 단일 AP 레이아웃",
    )
    p.add_argument(
        "--output-json",
        type=Path,
        default=_RF / "sample" / "output" / "layout_comparison_summary.json",
    )
    p.add_argument(
        "--output-md",
        type=Path,
        default=_RF / "sample" / "output" / "layout_comparison_summary.md",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run_layout_comparison(
        scene_path=args.scene,
        config_path=args.config,
        manual_layout_path=args.manual_layout,
        summary_json_path=args.output_json,
        summary_md_path=args.output_md,
    )
    print()
    print("=== Layout comparison (baseline) ===")
    print(f"Scene: {summary['scene_version_id']}  |  grid: {summary['grid_resolution_m']} m")
    print()
    print_comparison_table(summary["comparison_rows"])
    print()
    print("--- 해석 ---")
    print(summary["interpretation_ko"])
    print()
    print(f"JSON: {args.output_json.resolve()}")
    print(f"Markdown: {args.output_md.resolve()}")


if __name__ == "__main__":
    main()
