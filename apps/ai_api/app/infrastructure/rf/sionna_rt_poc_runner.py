from __future__ import annotations

from typing import Any

from packages.rf_core.adapters.sionna import sionna_input_dto_to_engine_plan


def build_sionna_rt_poc_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return sionna_input_dto_to_engine_plan(
        payload["input_data"],
        material_map=payload.get("material_map"),
        measurement_plane_z_m=float(payload.get("measurement_plane_z_m", 1.0)),
    )
