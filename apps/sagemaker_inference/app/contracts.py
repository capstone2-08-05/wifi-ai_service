"""계약 페이로드 파싱/빌더.

input.json 검증, result.json / failure.json 생성을 담당.
JSON Schema 는 컨테이너 이미지에 vendored copy 로 동봉 (schemas/ 디렉토리).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from app.constants import (
    CONTAINER_VERSION,
    SCHEMA_DIR,
    SCHEMA_VERSION,
    ErrorCode,
    ErrorStage,
    OutputFile,
)


def _load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


_INPUT_VALIDATOR = Draft202012Validator(_load_schema("input.schema.json"))


class ContractError(Exception):
    """input.json 검증 실패. code = INVALID_INPUT / UNSUPPORTED_SCHEMA_VERSION."""

    def __init__(self, code: ErrorCode, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class ParsedInput:
    """input.json 의 정규화된 형태."""

    job_id: str
    source_image_s3_uri: str
    output_prefix: str
    tasks: dict[str, bool]
    project_id: str | None = None
    floor_id: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def parse_input(payload_bytes: bytes) -> ParsedInput:
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise ContractError(
            ErrorCode.INVALID_INPUT,
            "input payload is not valid JSON",
            details={"json_error": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise ContractError(ErrorCode.INVALID_INPUT, "input payload must be a JSON object")

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ContractError(
            ErrorCode.UNSUPPORTED_SCHEMA_VERSION,
            f"unsupported schema_version: {version!r}; container expects {SCHEMA_VERSION!r}",
            details={"received": version, "supported": [SCHEMA_VERSION]},
        )

    errors = sorted(_INPUT_VALIDATOR.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        raise ContractError(
            ErrorCode.INVALID_INPUT,
            f"input schema violation at {list(first.absolute_path) or '<root>'}: {first.message}",
            details={
                "violations": [
                    {"path": list(e.absolute_path), "message": e.message}
                    for e in errors[:10]
                ]
            },
        )

    tasks = payload["tasks"]
    return ParsedInput(
        job_id=payload["job_id"],
        source_image_s3_uri=payload["source_image_s3_uri"],
        output_prefix=payload["output_prefix"],
        tasks={k: bool(v) for k, v in tasks.items()},
        project_id=payload.get("project_id"),
        floor_id=payload.get("floor_id"),
        options=payload.get("options") or {},
        metadata=payload.get("metadata") or {},
        raw=payload,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Stopwatch:
    """단계별 시간 측정."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self.stages: dict[str, int] = {}

    def mark(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = int((now - self._t0) * 1000)
        self._t0 = now


def normalize_output_prefix(output_prefix: str) -> str:
    """trailing slash 보장."""
    return output_prefix if output_prefix.endswith("/") else output_prefix + "/"


def build_result(
    *,
    parsed: ParsedInput,
    output_prefix: str,
    started_at_iso: str,
    stages: dict[str, int],
    image_size: tuple[int, int],
    device: str,
    unet_model: str | None,
    yolo_model: str | None,
) -> dict[str, Any]:
    width_px, height_px = image_size

    outputs = {
        f.uri_key: f"{output_prefix}{f.value}"
        for f in (
            OutputFile.RESULT,
            OutputFile.WALL_MASK,
            OutputFile.WALL_PROB_MAP,
            OutputFile.DETECTIONS,
            OutputFile.PREVIEW_OVERLAY,
        )
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "job_id": parsed.job_id,
        "project_id": parsed.project_id,
        "floor_id": parsed.floor_id,
        "started_at": started_at_iso,
        "completed_at": _now_iso(),
        "outputs": outputs,
        "stages": stages,
        "image": {
            "width_px": int(width_px),
            "height_px": int(height_px),
        },
        "runtime": {
            "container_version": CONTAINER_VERSION,
            "device": device,
            "unet_model": unet_model or "",
            "yolo_model": yolo_model or "",
        },
        "echo": dict(parsed.metadata),
    }


def build_failure(
    *,
    parsed: ParsedInput | None,
    started_at_iso: str | None,
    code: ErrorCode,
    stage: ErrorStage,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    partial_outputs: dict[str, str] | None = None,
    device: str | None = None,
    raw_payload_job_id: str | None = None,
) -> dict[str, Any]:
    job_id = parsed.job_id if parsed else (raw_payload_job_id or "unknown")
    project_id = parsed.project_id if parsed else None
    floor_id = parsed.floor_id if parsed else None
    echo = parsed.metadata if parsed else {}

    failure = {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "job_id": job_id,
        "project_id": project_id,
        "floor_id": floor_id,
        "failed_at": _now_iso(),
        "error": {
            "code": str(code),
            "stage": str(stage),
            "message": message,
            "retryable": retryable,
            "details": details or {},
        },
        "partial_outputs": partial_outputs or {},
        "runtime": {
            "container_version": CONTAINER_VERSION,
            "device": device or "",
        },
        "echo": dict(echo) if echo else {},
    }
    if started_at_iso:
        failure["started_at"] = started_at_iso
    return failure
