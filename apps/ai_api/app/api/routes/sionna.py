"""내부 Sionna 실행 API (인증·DB 본연동 없음, sionna_rt 기본).

이미지 서빙 라우트도 같이 제공 — Sionna 결과 PNG (heatmap/valid_mask/geometry_overlay) 를
브라우저가 직접 로드할 수 있도록 GET /internal/sionna/images/{sionna_run_id}/{filename} 노출.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.error_normalizers.sionna import normalize_sionna_exception
from app.api.error_responses.sionna import SIONNA_ERROR_RESPONSES
from app.infrastructure.ai_runtime.sionna_gateway import run_sionna_with_runtime
from app.infrastructure.settings import OUTPUT_DIR
from app.presentation.requests.sionna_request_dto import SionnaRunRequestDto
from app.presentation.responses.sionna_response_dto import (
    SionnaRunResponseDto,
    to_sionna_response,
)
from app.usecases.run_sionna_usecase import run_sionna_usecase

router = APIRouter()

# UUID4 형식만 허용 — path traversal 방어 (../ 등 차단).
_RUN_ID_PATTERN = re.compile(r"^[0-9a-fA-F\-]{8,64}$")
# 서빙 가능한 파일 화이트리스트.
_ALLOWED_FILES = {
    "radiomap_heatmap.png",            # clean overlay (캔버스 정렬용)
    "radiomap_heatmap_annotated.png",  # 디버그/사람 보기용 (chrome 포함)
    "valid_mask.png",
    "geometry_overlay.png",
}


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


@router.get(
    "/sionna/images/{sionna_run_id}.png",
    summary="Sionna RT heatmap PNG 직접 다운로드 (default: radiomap_heatmap.png)",
)
def get_sionna_heatmap_image(sionna_run_id: str) -> FileResponse:
    """기본 heatmap PNG. backend / 프론트가 <img src> 로 직접 로드."""
    return _serve_sionna_artifact(sionna_run_id, "radiomap_heatmap.png")


@router.get(
    "/sionna/images/{sionna_run_id}/{filename}",
    summary="Sionna RT 결과 PNG 명시적 파일명",
)
def get_sionna_artifact_image(sionna_run_id: str, filename: str) -> FileResponse:
    return _serve_sionna_artifact(sionna_run_id, filename)


def _serve_sionna_artifact(sionna_run_id: str, filename: str) -> FileResponse:
    if not _RUN_ID_PATTERN.match(sionna_run_id):
        raise HTTPException(status_code=400, detail="invalid sionna_run_id format")
    if filename not in _ALLOWED_FILES:
        raise HTTPException(status_code=404, detail=f"file not allowed: {filename}")
    path: Path = OUTPUT_DIR / "sionna" / "sionna_rt" / sionna_run_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}")
    return FileResponse(path, media_type="image/png")
