"""내부 RF 실행 API (인증·DB 본연동 없음, sionna_rt 기본)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_rf_preview_runner, get_sionna_rt_poc_runner
from app.api.errors import AppError, to_http_exception
from app.presentation.requests.rf_request_dto import RfRunRequestDto, SionnaRtPocRequestDto
from app.presentation.responses.rf_response_dto import (
    RfRunResponseDto,
    SionnaRtPocResponseDto,
    to_rf_response,
)
from app.usecases.run_rf_preview_usecase import run_rf_preview_usecase
from app.usecases.run_sionna_rt_poc_usecase import run_sionna_rt_poc_usecase

router = APIRouter()


@router.post("/rf/run", response_model=RfRunResponseDto)
def post_internal_rf_run(
    body: RfRunRequestDto,
    runner=Depends(get_rf_preview_runner),
) -> RfRunResponseDto:
    try:
        if body.engine != "sionna_rt":
            raise AppError(status_code=400, detail="only engine=sionna_rt is supported")
        result = run_rf_preview_usecase(body, runner)
        return to_rf_response(result)
    except Exception as exc:
        raise to_http_exception(exc) from exc


@router.post("/rf/sionna/poc", response_model=SionnaRtPocResponseDto)
def post_internal_rf_sionna_poc(
    body: SionnaRtPocRequestDto,
    runner=Depends(get_sionna_rt_poc_runner),
) -> SionnaRtPocResponseDto:
    try:
        plan = run_sionna_rt_poc_usecase(body, runner)
        return SionnaRtPocResponseDto(status="ok", engine="sionna_rt", plan=plan)
    except Exception as exc:
        raise to_http_exception(exc) from exc
