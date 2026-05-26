from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel

# imageUrl 템플릿 — env 로 ai_api 의 외부 노출 URL prefix 를 받는다.
# 예: http://localhost:9000/internal/sionna/images/{sionna_run_id}.png
# 미지정 시 기본값으로 :9000 가정 (ai_api 의 README/.env 기본 포트).
_DEFAULT_IMAGE_URL_TEMPLATE = (
    "http://localhost:9000/internal/sionna/images/{sionna_run_id}.png"
)


def _image_url_template() -> str:
    return os.getenv("SIONNA_ARTIFACT_IMAGE_URL_TEMPLATE", _DEFAULT_IMAGE_URL_TEMPLATE)


class SionnaRunResponseDto(BaseModel):
    sionna_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    imageUrl: str | None = None
    detail: str | None = None


def to_sionna_response(result: dict[str, Any]) -> SionnaRunResponseDto:
    """artifacts → DTO 변환. imageUrl 은 SIONNA_ARTIFACT_IMAGE_URL_TEMPLATE 기반의
    실제 HTTP URL — 로컬 FS 경로(visualization_path) 가 아님. 클라이언트가 <img src>
    로 바로 로드 가능.
    """
    artifacts = result.get("artifacts") or None
    sionna_run_id = str(result.get("sionna_run_id", ""))
    status = str(result.get("status", "failed"))

    image_url: str | None = None
    if artifacts is not None:
        # artifacts 에 미리 박힌 imageUrl 이 있으면 그걸 우선 사용 (테스트/오버라이드용).
        explicit = artifacts.get("imageUrl")
        if isinstance(explicit, str) and explicit:
            image_url = explicit

    # 결과가 성공이고 sionna_run_id 가 있으면 env 템플릿으로 URL 구성.
    # visualization_path (로컬 FS 경로) 는 클라이언트가 못 쓰므로 fallback 으로 안 씀.
    if image_url is None and status == "succeeded" and sionna_run_id:
        try:
            image_url = _image_url_template().format(sionna_run_id=sionna_run_id)
        except (KeyError, IndexError):
            image_url = None

    return SionnaRunResponseDto(
        sionna_run_id=sionna_run_id,
        status=status,
        metrics=result.get("metrics"),
        artifacts=artifacts,
        imageUrl=image_url,
        detail=result.get("error"),
    )
