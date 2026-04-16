from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from app.infrastructure.settings import OUTPUT_DIR, sionna_cell_size_m, sionna_samples_per_tx, sionna_seed
from packages.ai_runtime.sionna_adapter import sionna_input_dto_to_engine_plan
from packages.ai_runtime.sionna_runtime import run_sionna_rt_from_engine_plan


def _save_radiomap_png(rf_run_id: str, radiomap_dbm: list[list[float]]) -> str | None:
    try:
        arr = np.asarray(radiomap_dbm, dtype=float)
        # 유효 범위 밖(-270 dBm placeholder) 셀은 시각화에서 제외해 비교 왜곡을 줄인다.
        masked = np.ma.masked_where(arr <= -269.0, arr)
        out_dir = OUTPUT_DIR / "rf" / "sionna_rt" / rf_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "radiomap_heatmap.png"
        plt.figure(figsize=(6, 5))
        cmap = plt.get_cmap("inferno").copy()
        cmap.set_bad(color="#5a5a5a", alpha=1.0)
        plt.imshow(
            masked,
            origin="lower",
            cmap=cmap,
            vmin=-90.0,
            vmax=-30.0,
            interpolation="bicubic",
        )
        plt.colorbar(label="RSS (dBm), fixed range [-90, -30]")
        plt.title("Sionna RT RadioMap")
        plt.tight_layout()
        plt.savefig(out_path, dpi=140)
        plt.close()
        return str(Path(out_path).resolve())
    except Exception:
        return None


def _save_runtime_result_json(rf_run_id: str, runtime_result: dict[str, Any]) -> str | None:
    try:
        out_dir = OUTPUT_DIR / "rf" / "sionna_rt" / rf_run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "runtime_result.json"
        out_path.write_text(json.dumps(runtime_result, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(out_path.resolve())
    except Exception:
        return None


def run_rf_preview_with_rf_core(payload: dict[str, Any]) -> dict[str, Any]:
    rf_run_id = str(uuid.uuid4())
    engine = str(payload.get("engine", "sionna_rt"))
    run_type = payload.get("run_type", "preview")
    floor_id = payload.get("floor_id")
    input_data = payload["input_data"]

    if engine != "sionna_rt":
        raise ValueError("only engine=sionna_rt is supported")

    plan = sionna_input_dto_to_engine_plan(input_data)
    try:
        sionna_result = run_sionna_rt_from_engine_plan(
            plan,
            cell_size_m=sionna_cell_size_m(),
            samples_per_tx=sionna_samples_per_tx(),
            seed=sionna_seed(),
        )
    except ImportError as exc:
        return {
            "rf_run_id": rf_run_id,
            "status": "failed",
            "metrics": {"mode": "sionna_rt_runtime", "error": str(exc)},
            "artifacts": {},
            "output_root": "",
            "manifest": None,
            "paths": None,
            "error": f"ImportError: {exc}",
        }
    except Exception as exc:
        return {
            "rf_run_id": rf_run_id,
            "status": "failed",
            "metrics": {"mode": "sionna_rt_runtime", "error": str(exc)},
            "artifacts": {},
            "output_root": "",
            "manifest": None,
            "paths": None,
            "error": f"{type(exc).__name__}: {exc}",
        }

    visualization_path = _save_radiomap_png(rf_run_id, sionna_result["radiomap_dbm"])
    runtime_result_path = _save_runtime_result_json(rf_run_id, sionna_result)
    metrics = {
        "mode": "sionna_rt_runtime",
        "run_type": run_type,
        "floor_id": floor_id,
        "rssi_summary": sionna_result["rss_dbm"],
        "coverage_summary": sionna_result["coverage_summary"],
    }
    artifacts = {
        "engine": "sionna_rt",
        "radiomap": {
            "grid_shape": sionna_result["grid_shape"],
            "bounds_m": sionna_result["bounds_m"],
            "values_dbm": sionna_result["radiomap_dbm"],
        },
        "rssi": {
            **sionna_result["rss_dbm"],
            "center_cell_dbm": sionna_result["center_cell_rss_dbm"],
        },
        "coverage": sionna_result["coverage_summary"],
    }
    if visualization_path is not None:
        artifacts["visualization_path"] = visualization_path
    if runtime_result_path is not None:
        artifacts["runtime_result_path"] = runtime_result_path

    return {
        "rf_run_id": rf_run_id,
        "status": "succeeded",
        "metrics": metrics,
        "artifacts": artifacts,
        "output_root": "",
        "manifest": {
            "engine": "sionna_rt",
            "run_type": run_type,
            "floor_id": floor_id,
            "metrics": metrics,
            "artifacts": artifacts,
        },
        "paths": None,
        "error": None,
    }
