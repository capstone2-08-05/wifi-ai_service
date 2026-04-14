from __future__ import annotations

from typing import Any

from app.presentation.requests.rf_request_dto import RfRunRequestDto


def run_rf_preview_usecase(body: RfRunRequestDto, runner):
    payload: dict[str, Any] = {
        "run_type": body.run_type,
        "floor_id": body.floor_id,
        "baseline": body.baseline.model_dump(),
        "input_kind": body.input.kind,
    }

    if body.input.kind == "sionna_dto":
        payload["input_data"] = body.input.data
    else:
        payload["input_data"] = {
            "scene": body.input.scene,
            "ap_layout": body.input.ap_layout,
            "sim_config": body.input.sim_config,
        }

    return runner(payload)
