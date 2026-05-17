"""RF inference 계약 페이로드 파싱/빌더.

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
    DEFAULT_MAX_DEPTH,
    DEFAULT_MEASUREMENT_PLANE_Z_M,
    DEFAULT_RESOLUTION_M,
    DEFAULT_SAMPLES_PER_TX,
    DEFAULT_SEED,
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
class SimulationParams:
    """input.simulation 의 정규화된 형태 (기본값 적용 완료)."""

    frequency_hz: float
    tx_power_dbm: float
    resolution_m: float = DEFAULT_RESOLUTION_M
    measurement_plane_z_m: float = DEFAULT_MEASUREMENT_PLANE_Z_M
    max_depth: int = DEFAULT_MAX_DEPTH
    samples_per_tx: int = DEFAULT_SAMPLES_PER_TX
    seed: int = DEFAULT_SEED


@dataclass
class AccessPoint:
    id: str
    x_m: float
    y_m: float
    z_m: float


@dataclass
class ParsedInput:
    """input.json 의 정규화된 형태."""

    job_id: str
    scene_s3_uri: str
    output_prefix: str
    simulation: SimulationParams
    access_points: list[AccessPoint]
    project_id: str | None = None
    floor_id: str | None = None
    scene_version_id: str | None = None
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

    sim_raw = payload["simulation"]
    simulation = SimulationParams(
        frequency_hz=float(sim_raw["frequency_hz"]),
        tx_power_dbm=float(sim_raw["tx_power_dbm"]),
        resolution_m=float(sim_raw.get("resolution_m", DEFAULT_RESOLUTION_M)),
        measurement_plane_z_m=float(
            sim_raw.get("measurement_plane_z_m", DEFAULT_MEASUREMENT_PLANE_Z_M)
        ),
        max_depth=int(sim_raw.get("max_depth", DEFAULT_MAX_DEPTH)),
        samples_per_tx=int(sim_raw.get("samples_per_tx", DEFAULT_SAMPLES_PER_TX)),
        seed=int(sim_raw.get("seed", DEFAULT_SEED)),
    )

    access_points = [
        AccessPoint(
            id=str(ap["id"]),
            x_m=float(ap["x_m"]),
            y_m=float(ap["y_m"]),
            z_m=float(ap["z_m"]),
        )
        for ap in payload["access_points"]
    ]

    return ParsedInput(
        job_id=payload["job_id"],
        scene_s3_uri=payload["scene_s3_uri"],
        output_prefix=payload["output_prefix"],
        simulation=simulation,
        access_points=access_points,
        project_id=payload.get("project_id"),
        floor_id=payload.get("floor_id"),
        scene_version_id=payload.get("scene_version_id"),
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
    radio_map_meta: dict[str, Any],
    device: str,
    engine: str,
    sionna_version: str | None = None,
) -> dict[str, Any]:
    outputs = {
        f.uri_key: f"{output_prefix}{f.value}"
        for f in (OutputFile.RESULT, OutputFile.HEATMAP, OutputFile.RADIO_MAP)
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "completed",
        "job_id": parsed.job_id,
        "project_id": parsed.project_id,
        "floor_id": parsed.floor_id,
        "scene_version_id": parsed.scene_version_id,
        "started_at": started_at_iso,
        "completed_at": _now_iso(),
        "outputs": outputs,
        "stages": stages,
        "radio_map": radio_map_meta,
        "access_points": [
            {"id": ap.id, "x_m": ap.x_m, "y_m": ap.y_m, "z_m": ap.z_m}
            for ap in parsed.access_points
        ],
        "runtime": {
            "container_version": CONTAINER_VERSION,
            "device": device,
            "engine": engine,
            "sionna_version": sionna_version or "",
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
    engine: str | None = None,
) -> dict[str, Any]:
    job_id = parsed.job_id if parsed else "unknown"
    project_id = parsed.project_id if parsed else None
    floor_id = parsed.floor_id if parsed else None
    scene_version_id = parsed.scene_version_id if parsed else None
    echo = parsed.metadata if parsed else {}

    failure = {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "job_id": job_id,
        "project_id": project_id,
        "floor_id": floor_id,
        "scene_version_id": scene_version_id,
        "failed_at": _now_iso(),
        "error": {
            "code": code.value,
            "stage": stage.value,
            "message": message,
            "retryable": retryable,
            "details": details or {},
        },
        "partial_outputs": partial_outputs or {},
        "runtime": {
            "container_version": CONTAINER_VERSION,
            "device": device or "",
            "engine": engine or "",
        },
        "echo": dict(echo) if echo else {},
    }
    if started_at_iso:
        failure["started_at"] = started_at_iso
    return failure
