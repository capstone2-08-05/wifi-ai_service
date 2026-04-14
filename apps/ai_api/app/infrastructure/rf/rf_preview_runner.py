from packages.rf_core.services.rf_run_service import run_rf

from app.presentation.requests.rf_request_dto import RfRunRequestDto


def run_rf_preview_with_rf_core(body: RfRunRequestDto):
    b = body.baseline
    if body.input.kind == "sionna_dto":
        return run_rf(
            engine="baseline",
            run_type=body.run_type,
            floor_id=body.floor_id,
            input_mode="sionna_dto",
            sionna_payload=body.input.data,
            grid_resolution_m=b.grid_resolution_m,
            path_loss_constant_db=b.path_loss_constant_db,
            path_loss_exponent=b.path_loss_exponent,
            include_exterior_walls=b.include_exterior_walls,
            output_dir_name=b.output_dir_name,
            antenna_z_policy=b.antenna_z_policy,
            default_antenna_z_m=b.default_antenna_z_m,
            layout_name=b.layout_name,
            layout_type=b.layout_type,
            skip_heatmap=b.skip_heatmap,
            persist_outputs=False,
        )

    inp = body.input
    return run_rf(
        engine="baseline",
        run_type=body.run_type,
        floor_id=body.floor_id,
        input_mode="rf_canonical",
        scene_dict=inp.scene,
        ap_layout_dict=inp.ap_layout,
        sim_config_dict=inp.sim_config,
        grid_resolution_m=b.grid_resolution_m,
        path_loss_constant_db=b.path_loss_constant_db,
        path_loss_exponent=b.path_loss_exponent,
        include_exterior_walls=b.include_exterior_walls,
        output_dir_name=b.output_dir_name,
        skip_heatmap=b.skip_heatmap,
        persist_outputs=False,
    )
