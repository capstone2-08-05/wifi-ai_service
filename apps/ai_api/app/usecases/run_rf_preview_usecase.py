from __future__ import annotations

from typing import Any

from app.presentation.requests.rf_request_dto import RfRunRequestDto


def run_rf_preview_usecase(body: RfRunRequestDto, runner):
    payload: dict[str, Any] = {
        "engine": body.engine,
        "run_type": body.run_type,
        "floor_id": body.floor_id,
        "input_data": body.input.data,
    }

    return runner(payload)
