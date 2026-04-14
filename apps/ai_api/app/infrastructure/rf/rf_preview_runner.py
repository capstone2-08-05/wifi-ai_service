from __future__ import annotations

from typing import Any

from packages.rf_core.services.rf_run_service import run_rf


def run_rf_preview_with_rf_core(payload: dict[str, Any]):
    baseline = payload["baseline"]
    run_type = payload["run_type"]
    floor_id = payload["floor_id"]
    input_kind = payload["input_kind"]
    input_data = payload["input_data"]

    if input_kind == "sionna_dto":
        return run_rf(
            engine="baseline",
            run_type=run_type,
            floor_id=floor_id,
            input_mode="sionna_dto",
            sionna_payload=input_data,
            grid_resolution_m=baseline["grid_resolution_m"],
            path_loss_constant_db=baseline["path_loss_constant_db"],
            path_loss_exponent=baseline["path_loss_exponent"],
            include_exterior_walls=baseline["include_exterior_walls"],
            output_dir_name=baseline["output_dir_name"],
            antenna_z_policy=baseline["antenna_z_policy"],
            default_antenna_z_m=baseline["default_antenna_z_m"],
            layout_name=baseline["layout_name"],
            layout_type=baseline["layout_type"],
            skip_heatmap=baseline["skip_heatmap"],
            persist_outputs=False,
        )

    canonical = input_data
    return run_rf(
        engine="baseline",
        run_type=run_type,
        floor_id=floor_id,
        input_mode="rf_canonical",
        scene_dict=canonical["scene"],
        ap_layout_dict=canonical["ap_layout"],
        sim_config_dict=canonical["sim_config"],
        grid_resolution_m=baseline["grid_resolution_m"],
        path_loss_constant_db=baseline["path_loss_constant_db"],
        path_loss_exponent=baseline["path_loss_exponent"],
        include_exterior_walls=baseline["include_exterior_walls"],
        output_dir_name=baseline["output_dir_name"],
        skip_heatmap=baseline["skip_heatmap"],
        persist_outputs=False,
    )
