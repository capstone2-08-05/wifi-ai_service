"""RF 실행 결과 DTO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class RfOutputPaths:
    """실행 산출물 절대 경로 (API 응답에서 바로 확인용)."""

    output_dir: str
    manifest: str
    heatmap: str | None
    summary: str


@dataclass(frozen=True)
class RfRunResult:
    rf_run_id: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] | None
    artifacts: dict[str, Any]
    output_root: str
    manifest: dict[str, Any] | None
    paths: RfOutputPaths | None = None
    error: str | None = None
