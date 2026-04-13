from __future__ import annotations

"""JSON 파일 3종에 RF 실행 이력을 쌓는 프로토타입 저장소.

`baseline_rf_simulator.py`가 만드는 `run_manifest.json`과의 대응 관계:

- **rf_runs.json** 한 행 ≈ 시뮬 1회. `metrics_json`은 manifest의 `metrics`와 동일.
  `sim_config_json`은 manifest의 `config` + `output_dir_name` 등 실행에 쓴 설정.
  `output_root`는 결과 디렉터리(`.npy`, `run_manifest.json`이 들어 있는 폴더).
- **ap_layouts.json** 한 행 ≈ 그 실행에 사용한 AP 배치. `placements_json`은 AP 좌표·전력 요약
  (CLI에서 `save_ap_layout`에 넘기는 dict 리스트).
- **rf_maps.json** 여러 행 ≈ manifest `artifacts`에 나열된 파일 각각.
  `map_type`은 내부 라벨(`rssi_strongest`, `heatmap_png` 등),
  `storage_url`은 로컬 절대 경로 문자열(데모용).
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RfRunRecord:
    id: str
    scene_version_id: str
    floor_id: str
    run_type: str
    engine_name: str
    engine_version: str
    status: str
    sim_config_json: dict[str, Any]
    metrics_json: dict[str, Any] | None
    output_root: str
    started_at: str
    finished_at: str | None = None
    project_id: str | None = None
    job_id: str | None = None
    ap_candidates_json: list[dict[str, Any]] | None = None


@dataclass
class ApLayoutRecord:
    id: str
    rf_run_id: str
    layout_name: str
    layout_type: str
    total_ap_count: int
    placements_json: list[dict[str, Any]]


@dataclass
class RfMapRecord:
    id: str
    rf_run_id: str
    map_type: str
    storage_url: str
    bounds_json: dict[str, Any]
    resolution_m: float
    metadata_json: dict[str, Any] | None = None


class JsonPersistenceStore:
    """Prototype persistence: rf_runs / ap_layouts / rf_maps as JSON lists (no DB)."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

        self.rf_runs_path = self.root_dir / "rf_runs.json"
        self.ap_layouts_path = self.root_dir / "ap_layouts.json"
        self.rf_maps_path = self.root_dir / "rf_maps.json"

        for path in (self.rf_runs_path, self.ap_layouts_path, self.rf_maps_path):
            if not path.exists():
                path.write_text("[]", encoding="utf-8")

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_list(self, path: Path, items: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def create_rf_run(
        self,
        *,
        scene_version_id: str,
        floor_id: str,
        run_type: str,
        engine_name: str,
        sim_config_json: dict[str, Any],
        output_root: str,
        engine_version: str = "baseline-0.1",
        project_id: str | None = None,
        job_id: str | None = None,
        ap_candidates_json: list[dict[str, Any]] | None = None,
        rf_run_id: str | None = None,
    ) -> RfRunRecord:
        record = RfRunRecord(
            id=rf_run_id if rf_run_id else str(uuid.uuid4()),
            scene_version_id=scene_version_id,
            floor_id=floor_id,
            run_type=run_type,
            engine_name=engine_name,
            engine_version=engine_version,
            status="running",
            sim_config_json=sim_config_json,
            metrics_json=None,
            output_root=output_root,
            started_at=utc_now_iso(),
            project_id=project_id,
            job_id=job_id,
            ap_candidates_json=ap_candidates_json,
        )
        items = self._read_list(self.rf_runs_path)
        items.append(asdict(record))
        self._write_list(self.rf_runs_path, items)
        return record

    def finish_rf_run(
        self,
        *,
        rf_run_id: str,
        status: str,
        metrics_json: dict[str, Any],
    ) -> None:
        items = self._read_list(self.rf_runs_path)
        for item in items:
            if item["id"] == rf_run_id:
                item["status"] = status
                item["metrics_json"] = metrics_json
                item["finished_at"] = utc_now_iso()
                break
        self._write_list(self.rf_runs_path, items)

    def save_ap_layout(
        self,
        *,
        rf_run_id: str,
        layout_name: str,
        layout_type: str,
        placements_json: list[dict[str, Any]],
    ) -> ApLayoutRecord:
        record = ApLayoutRecord(
            id=str(uuid.uuid4()),
            rf_run_id=rf_run_id,
            layout_name=layout_name,
            layout_type=layout_type,
            total_ap_count=len(placements_json),
            placements_json=placements_json,
        )
        items = self._read_list(self.ap_layouts_path)
        items.append(asdict(record))
        self._write_list(self.ap_layouts_path, items)
        return record

    def save_rf_map(
        self,
        *,
        rf_run_id: str,
        map_type: str,
        storage_url: str,
        bounds_json: dict[str, Any],
        resolution_m: float,
        metadata_json: dict[str, Any] | None = None,
    ) -> RfMapRecord:
        record = RfMapRecord(
            id=str(uuid.uuid4()),
            rf_run_id=rf_run_id,
            map_type=map_type,
            storage_url=storage_url,
            bounds_json=bounds_json,
            resolution_m=resolution_m,
            metadata_json=metadata_json,
        )
        items = self._read_list(self.rf_maps_path)
        items.append(asdict(record))
        self._write_list(self.rf_maps_path, items)
        return record

    def save_maps_from_manifest(
        self,
        *,
        rf_run_id: str,
        manifest: dict[str, Any],
        output_dir: Path,
    ) -> None:
        bounds_json = manifest["bounds"]
        resolution_m = manifest["config"]["grid_resolution_m"]
        artifacts = manifest["artifacts"]

        mapping = {
            "strongest_rssi_map": "rssi_strongest",
            "strongest_path_loss_map": "path_loss_strongest",
            "strongest_wall_loss_map": "wall_loss_strongest",
            "best_server_map": "best_server",
            "heatmap_png": "heatmap_png",
        }

        for manifest_key, map_type in mapping.items():
            if manifest_key in artifacts:
                self.save_rf_map(
                    rf_run_id=rf_run_id,
                    map_type=map_type,
                    storage_url=str((output_dir / artifacts[manifest_key]).resolve()),
                    bounds_json=bounds_json,
                    resolution_m=resolution_m,
                )

        for ap_id, filename in artifacts.get("per_ap_rssi_maps", {}).items():
            self.save_rf_map(
                rf_run_id=rf_run_id,
                map_type="rssi_per_ap",
                storage_url=str((output_dir / filename).resolve()),
                bounds_json=bounds_json,
                resolution_m=resolution_m,
                metadata_json={"ap_id": ap_id},
            )
