from __future__ import annotations

from typing import Any

from app.presentation.requests.rf_request_dto import SionnaRtPocRequestDto
from packages.rf_core.adapters.sionna import sionna_input_dto_to_engine_plan


def build_sionna_rt_poc_plan(body: SionnaRtPocRequestDto) -> dict[str, Any]:
    return sionna_input_dto_to_engine_plan(
        body.input.data,
        material_map=body.material_map,
        measurement_plane_z_m=body.measurement_plane_z_m,
    )
