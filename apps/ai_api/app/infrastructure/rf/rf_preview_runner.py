from __future__ import annotations

import uuid
from typing import Any

from packages.rf_core.adapters.sionna import sionna_input_dto_to_engine_plan
from packages.rf_core.services.rf_run_service import RfRunResult


def run_rf_preview_with_rf_core(payload: dict[str, Any]):
    engine = str(payload.get("engine", "sionna_rt"))
    run_type = payload.get("run_type", "preview")
    floor_id = payload.get("floor_id")
    input_data = payload["input_data"]

    if engine != "sionna_rt":
        raise ValueError("only engine=sionna_rt is supported")

    plan = sionna_input_dto_to_engine_plan(input_data)
    metrics = {
        "mode": "sionna_rt_plan",
        "run_type": run_type,
        "floor_id": floor_id,
        "note": "Sionna RT execution integration pending; returning validated engine plan.",
    }
    return RfRunResult(
        rf_run_id=str(uuid.uuid4()),
        status="succeeded",
        metrics=metrics,
        artifacts={"engine": "sionna_rt", "engine_plan": plan},
        output_root="",
        manifest={
            "engine": "sionna_rt",
            "metrics": metrics,
            "artifacts": {"engine_plan": plan},
        },
        paths=None,
        error=None,
    )
