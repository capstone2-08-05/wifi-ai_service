from __future__ import annotations

from typing import Any

from app.presentation.requests.rf_request_dto import SionnaRtPocRequestDto


def run_sionna_rt_poc_usecase(body: SionnaRtPocRequestDto, runner) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "input_data": body.input.data,
        "measurement_plane_z_m": body.measurement_plane_z_m,
        "material_map": body.material_map,
    }
    return runner(payload)
