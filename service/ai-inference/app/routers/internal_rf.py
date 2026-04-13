"""내부 RF 실행 API (인증·DB 본연동 없음, baseline preview)."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.rf.services.rf_run_service import RfRunResult, run_rf

router = APIRouter()


class RfRunPaths(BaseModel):
    """성공 시 저장된 파일 절대 경로 (Windows/Linux 모두 문자열)."""

    output_dir: str
    manifest: str
    heatmap: str | None = None
    summary: str


class BaselineParams(BaseModel):
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


class InputSionnaDto(BaseModel):
    kind: Literal["sionna_dto"] = "sionna_dto"
    """`SionnaInputDTO` 와 동일 구조 (`config`, `antenna`, `scene`)."""
    data: dict[str, Any]


class InputRfCanonical(BaseModel):
    kind: Literal["rf_canonical"] = "rf_canonical"
    scene: dict[str, Any]
    ap_layout: dict[str, Any]
    sim_config: dict[str, Any]


class RfRunRequest(BaseModel):
    engine: Literal["baseline"] = "baseline"
    run_type: str = "preview"
    floor_id: str | None = None
    baseline: BaselineParams = Field(default_factory=BaselineParams)
    input: Annotated[Union[InputSionnaDto, InputRfCanonical], Field(discriminator="kind")]


class RfRunResponse(BaseModel):
    rf_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    output_root: str | None = None
    """실행 루트(``runs/<rf_run_id>/``). 산출물은 보통 ``output_root/<output_dir_name>/`` 아래."""
    paths: RfRunPaths | None = None
    detail: str | None = None


def _to_response(r: RfRunResult) -> RfRunResponse:
    paths: RfRunPaths | None = None
    if r.status == "succeeded" and r.paths is not None:
        p = r.paths
        paths = RfRunPaths(
            output_dir=p.output_dir,
            manifest=p.manifest,
            heatmap=p.heatmap,
            summary=p.summary,
        )
    return RfRunResponse(
        rf_run_id=r.rf_run_id,
        status=r.status,
        metrics=r.metrics,
        artifacts=r.artifacts if r.artifacts else None,
        output_root=r.output_root or None,
        paths=paths,
        detail=r.error,
    )


@router.post("/rf/run", response_model=RfRunResponse)
def post_internal_rf_run(body: RfRunRequest) -> RfRunResponse:
    if body.engine != "baseline":
        return RfRunResponse(
            rf_run_id="",
            status="failed",
            metrics=None,
            artifacts=None,
            output_root=None,
            paths=None,
            detail="only engine=baseline is supported",
        )
    b = body.baseline
    if body.input.kind == "sionna_dto":
        result = run_rf(
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
        )
    else:
        inp = body.input
        result = run_rf(
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
        )

    return _to_response(result)
