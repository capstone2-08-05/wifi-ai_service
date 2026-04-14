"""
RF 실행 단일 진입점 (팀 연동·API 래핑용).

`run_rf(...)` 가 DTO 수신 → (adapter) → baseline 시뮬 → heatmap/manifest 저장 → 결과 dict 반환.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from app.rf.adapters.baseline import sionna_input_dto_to_baseline_scene_and_layout
from app.rf.dto.backend_scene import SionnaInputDTO
from app.rf.models.rf_models import ApLayout, Scene, SimulationConfig
from app.rf.persistence.rf_persistence import JsonPersistenceStore
from app.rf.simulation.baseline_rf_simulator import BaselineRfSimulator, save_outputs


def _write_run_summary(
    output_dir: Path,
    rf_run_id: str,
    manifest: dict[str, Any],
) -> None:
    m = manifest.get("metrics") or {}
    payload = {
        "rf_run_id": rf_run_id,
        "status": "succeeded",
        "scene_version_id": manifest.get("scene_version_id"),
        "layout_name": manifest.get("layout_name"),
        "rssi_summary": m.get("rssi_summary"),
        "coverage_summary": m.get("coverage_summary"),
        "artifact_filenames": manifest.get("artifacts"),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_storage_root() -> Path:
    env = os.environ.get("RF_STORAGE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # app/rf/services/rf_run_service.py → parents[3] = ai-inference 서비스 루트
    return Path(__file__).resolve().parents[3] / "data" / "rf"


@dataclass(frozen=True)
class RfOutputPaths:
    """실행 산출물 절대 경로 (API 응답에서 바로 확인용)."""

    output_dir: str
    manifest: str
    heatmap: str | None
    summary: str


@dataclass(frozen=True)
class RfRunResult:
    rf_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None
    artifacts: dict[str, Any]
    output_root: str
    manifest: dict[str, Any] | None
    paths: RfOutputPaths | None = None
    error: str | None = None


def run_rf(
    *,
    engine: Literal["baseline"] = "baseline",
    run_type: str = "preview",
    floor_id: str | None = None,
    storage_root: Path | None = None,
    input_mode: Literal["sionna_dto", "rf_canonical"],
    sionna_payload: Mapping[str, Any] | None = None,
    scene_dict: Mapping[str, Any] | None = None,
    ap_layout_dict: Mapping[str, Any] | None = None,
    sim_config_dict: Mapping[str, Any] | None = None,
    grid_resolution_m: float = 0.25,
    path_loss_constant_db: float = 63.0,
    path_loss_exponent: float = 2.0,
    include_exterior_walls: bool = False,
    output_dir_name: str = "output",
    antenna_z_policy: Literal["ignore", "use_position_z"] = "ignore",
    default_antenna_z_m: float = 2.5,
    layout_name: str = "api_manual",
    layout_type: str = "manual",
    skip_heatmap: bool = False,
) -> RfRunResult:
    """
    Baseline RF 한 번 실행 후 로컬 디스크에 manifest·heatmap 등을 저장한다.

    - ``input_mode == "sionna_dto"``: ``sionna_payload`` 에 ``SionnaInputDTO`` JSON.
    - ``input_mode == "rf_canonical"``: 이미 RF canonical 인 ``scene_dict`` / ``ap_layout_dict`` / ``sim_config_dict``.

    DTO 경로에서 그리드·경로손실 등은 인자로 주어지며, canonical 경로에서는 ``sim_config_dict`` 에
    ``scene_version_id`` 가 있으면 씬과 일치해야 한다.
    """
    if engine != "baseline":
        raise ValueError(f"unsupported engine: {engine!r} (only 'baseline' for now)")

    root = storage_root or _default_storage_root()
    runs_dir = root / "runs"
    persistence_root = root / "persistence"
    runs_dir.mkdir(parents=True, exist_ok=True)
    persistence_root.mkdir(parents=True, exist_ok=True)

    store = JsonPersistenceStore(persistence_root)

    scene: Scene
    layout: ApLayout
    config: SimulationConfig

    try:
        if input_mode == "sionna_dto":
            if sionna_payload is None:
                raise ValueError("sionna_payload is required for input_mode=sionna_dto")
            dto = SionnaInputDTO.model_validate(sionna_payload)
            scene_d, layout_d = sionna_input_dto_to_baseline_scene_and_layout(
                dto,
                floor_id=floor_id,
                antenna_z_policy=antenna_z_policy,
                default_antenna_z_m=default_antenna_z_m,
                layout_name=layout_name,
                layout_type=layout_type,
            )
            scene = Scene.from_dict(dict(scene_d))
            layout = ApLayout.from_dict(dict(layout_d))
            sv = scene.scene_version_id
            config = SimulationConfig.from_dict(
                {
                    "scene_version_id": sv,
                    "grid_resolution_m": grid_resolution_m,
                    "path_loss_constant_db": path_loss_constant_db,
                    "path_loss_exponent": path_loss_exponent,
                    "include_exterior_walls": include_exterior_walls,
                    "output_dir_name": output_dir_name,
                }
            )
        else:
            if scene_dict is None or ap_layout_dict is None or sim_config_dict is None:
                raise ValueError(
                    "scene_dict, ap_layout_dict, sim_config_dict required for input_mode=rf_canonical"
                )
            scene = Scene.from_dict(dict(scene_dict))
            layout = ApLayout.from_dict(dict(ap_layout_dict))
            base_cfg = dict(sim_config_dict)
            base_cfg.setdefault("scene_version_id", scene.scene_version_id)
            base_cfg.setdefault("grid_resolution_m", grid_resolution_m)
            base_cfg.setdefault("path_loss_constant_db", path_loss_constant_db)
            base_cfg.setdefault("path_loss_exponent", path_loss_exponent)
            base_cfg.setdefault("include_exterior_walls", include_exterior_walls)
            base_cfg.setdefault("output_dir_name", output_dir_name)
            config = SimulationConfig.from_dict(base_cfg)

        floor = floor_id.strip() if isinstance(floor_id, str) and floor_id.strip() else (
            scene.floor_id or "unknown_floor"
        )

        rf_run_id = str(uuid.uuid4())
        run_output_root = runs_dir / rf_run_id
        output_dir = run_output_root / output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        store.create_rf_run(
            scene_version_id=scene.scene_version_id,
            floor_id=floor,
            run_type=run_type,
            engine_name="baseline",
            engine_version="baseline-0.1",
            sim_config_json={
                "grid_resolution_m": config.grid_resolution_m,
                "path_loss_constant_db": config.path_loss_constant_db,
                "path_loss_exponent": config.path_loss_exponent,
                "include_exterior_walls": config.include_exterior_walls,
                "output_dir_name": config.output_dir_name,
            },
            output_root=str(run_output_root.resolve()),
            rf_run_id=rf_run_id,
        )

        simulator = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
        result = simulator.run()
        manifest = save_outputs(
            scene=scene,
            ap_layout=layout,
            config=config,
            result=result,
            output_dir=output_dir,
            skip_heatmap=skip_heatmap,
        )
        _write_run_summary(output_dir, rf_run_id, manifest)

        manifest_path = str((output_dir / "run_manifest.json").resolve())
        summary_path = str((output_dir / "run_summary.json").resolve())
        heatmap_name = manifest.get("artifacts", {}).get("heatmap_png")
        heatmap_path = (
            str((output_dir / heatmap_name).resolve()) if heatmap_name else None
        )
        path_bundle = RfOutputPaths(
            output_dir=str(output_dir.resolve()),
            manifest=manifest_path,
            heatmap=heatmap_path,
            summary=summary_path,
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
            rf_run_id=rf_run_id,
            layout_name=layout.layout_name,
            layout_type=layout.layout_type,
            placements_json=placements_json,
        )
        store.finish_rf_run(
            rf_run_id=rf_run_id,
            status="succeeded",
            metrics_json=manifest["metrics"],
        )
        store.save_maps_from_manifest(
            rf_run_id=rf_run_id,
            manifest=manifest,
            output_dir=output_dir,
        )

        return RfRunResult(
            rf_run_id=rf_run_id,
            status="succeeded",
            metrics=manifest["metrics"],
            artifacts=manifest["artifacts"],
            output_root=str(run_output_root.resolve()),
            manifest=manifest,
            paths=path_bundle,
            error=None,
        )
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        return RfRunResult(
            rf_run_id=str(uuid.uuid4()),
            status="failed",
            metrics={"error": err_msg},
            artifacts={},
            output_root="",
            manifest=None,
            paths=None,
            error=err_msg,
        )
