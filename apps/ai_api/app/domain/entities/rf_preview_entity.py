from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class RfRunPathsEntity(BaseModel):
    output_dir: str
    manifest: str
    heatmap: str | None = None
    summary: str


class BaselineParamsEntity(BaseModel):
    grid_resolution_m: float = 0.25
    path_loss_constant_db: float = 63.0
    path_loss_exponent: float = 2.0
    include_exterior_walls: bool = False
    output_dir_name: str = "output"
    antenna_z_policy: Literal["ignore", "use_position_z"] = "ignore"
    default_antenna_z_m: float = 2.5
    layout_name: str = "api_manual"
    layout_type: str = "manual"
    skip_heatmap: bool = False


class InputSionnaPayloadEntity(BaseModel):
    kind: Literal["sionna_dto"] = "sionna_dto"
    data: dict[str, Any]


class InputRfCanonicalEntity(BaseModel):
    kind: Literal["rf_canonical"] = "rf_canonical"
    scene: dict[str, Any]
    ap_layout: dict[str, Any]
    sim_config: dict[str, Any]
