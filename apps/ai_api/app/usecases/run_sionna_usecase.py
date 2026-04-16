from __future__ import annotations

from typing import Any

from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto


def run_sionna_usecase(body: SionnaRunRequestDto, runner):
    payload: dict[str, Any] = {
        "engine": body.engine,
        "run_type": body.run_type,
        "floor_id": body.floor_id,
        "input_data": body.input.data,
    }

    return runner(payload)
