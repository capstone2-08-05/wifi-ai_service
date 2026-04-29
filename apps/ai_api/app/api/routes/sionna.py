"""내부 Sionna 실행 API (인증·DB 본연동 없음, sionna_rt 기본)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.error_normalizers.sionna import normalize_sionna_exception
from app.api.error_responses.sionna import SIONNA_ERROR_RESPONSES
from app.infrastructure.ai_runtime.sionna_gateway import run_sionna_with_runtime
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto
from app.presentation.responses.sionna_response_dto import (
    SionnaRunResponseDto,
    to_sionna_response,
)
from app.usecases.run_sionna_usecase import run_sionna_usecase

router = APIRouter()


@router.post(
    "/sionna/run",
    response_model=SionnaRunResponseDto,
    responses=SIONNA_ERROR_RESPONSES,
)
def post_internal_sionna_run(body: SionnaRunRequestDto) -> SionnaRunResponseDto:
    try:
        result = run_sionna_usecase(body, run_sionna_with_runtime)
    except Exception as exc:
        raise normalize_sionna_exception(exc, body=body) from exc
    return to_sionna_response(result)
