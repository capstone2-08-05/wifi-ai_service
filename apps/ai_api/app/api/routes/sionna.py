"""내부 Sionna 실행 API (인증·DB 본연동 없음, sionna_rt 기본)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_sionna_preview_runner
from app.api.errors import AppError, to_http_exception
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto
from app.presentation.responses.sionna_response_dto import (
    SionnaRunResponseDto,
    to_sionna_response,
)
from app.usecases.run_sionna_preview_usecase import run_sionna_preview_usecase

router = APIRouter()


@router.post("/sionna/run", response_model=SionnaRunResponseDto)
def post_internal_sionna_run(
    body: SionnaRunRequestDto,
    runner=Depends(get_sionna_preview_runner),
) -> SionnaRunResponseDto:
    try:
        if body.engine != "sionna_rt":
            raise AppError(status_code=400, detail="only engine=sionna_rt is supported")
        result = run_sionna_preview_usecase(body, runner)
        if result.get("status") == "failed":
            raise AppError(status_code=500, detail=result.get("error") or "Sionna RT run failed")
    except Exception as exc:
        raise to_http_exception(exc) from exc
    return to_sionna_response(result)
