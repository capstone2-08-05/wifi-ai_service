"""SageMaker /invocations 한 번의 처리 오케스트레이션 (RF).

input.json → scene.json S3 다운로드 → Sionna RT → 출력 3종 S3 PUT.
실패 시 failure.json 을 S3 PUT 하고 ContractError/HandlerError 로 raise.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.constants import ErrorCode, ErrorStage, OutputFile, StageMs
from app.contracts import (
    ContractError,
    ParsedInput,
    Stopwatch,
    _now_iso,
    build_failure,
    build_result,
    normalize_output_prefix,
    parse_input,
)
from app.postprocess import encode_heatmap_png
from app.runtime import default_device, run_simulation_for_all_aps, sionna_version_str
from app.s3_io import download_bytes, upload_json, upload_npy, upload_png

logger = logging.getLogger(__name__)


class HandlerError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        stage: ErrorStage,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.message = message
        self.retryable = retryable
        self.details = details or {}


def handle_invocation(payload_bytes: bytes) -> dict[str, Any]:
    """SageMaker /invocations 한 번 처리. 성공 시 result.json dict 반환."""
    t0 = time.perf_counter()
    started_at_iso = _now_iso()
    parsed: ParsedInput | None = None
    output_prefix: str | None = None
    partial: dict[str, str] = {}
    device_resolved = default_device()
    engine_used = "sionna_rt"

    try:
        # 1) 입력 검증
        parsed = parse_input(payload_bytes)
        output_prefix = normalize_output_prefix(parsed.output_prefix)

        sw = Stopwatch()

        # 2) scene.json 다운로드
        try:
            scene_bytes = download_bytes(parsed.scene_s3_uri)
        except Exception as exc:
            raise HandlerError(
                ErrorCode.SCENE_DOWNLOAD_FAILED,
                ErrorStage.DOWNLOAD_SCENE,
                f"S3 GetObject failed for scene.json: {exc}",
                retryable=True,
                details={"scene_s3_uri": parsed.scene_s3_uri},
            ) from exc
        sw.mark(StageMs.DOWNLOAD_SCENE.value)

        # 3) scene.json 파싱
        try:
            scene_dict = json.loads(scene_bytes)
            if not isinstance(scene_dict, dict):
                raise ValueError("scene.json root must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise HandlerError(
                ErrorCode.SCENE_PARSE_FAILED,
                ErrorStage.PARSE_SCENE,
                f"scene.json parse failed: {exc}",
                retryable=False,
                details={"scene_s3_uri": parsed.scene_s3_uri},
            ) from exc
        sw.mark(StageMs.PARSE_SCENE.value)

        # 4) Sionna RT 실행 (AP 별 → 셀별 max 집계)
        try:
            sim_out = run_simulation_for_all_aps(parsed, scene_dict)
        except Exception as exc:
            # CloudWatch 에 full traceback 명시 기록 — wrap 된 메시지만 보면
            # Dr.Jit 같은 내부 라이브러리의 진짜 에러 위치가 가려져서 진단 불가.
            logger.exception(
                "[RF_ERROR] Sionna RT failed at ray_tracing stage "
                "(num_aps=%d, num_walls=%d)",
                len(parsed.access_points),
                len(scene_dict.get("walls") or []),
            )
            raise HandlerError(
                ErrorCode.SIMULATION_FAILED,
                ErrorStage.RAY_TRACING,
                f"Sionna RT failed: {exc}",
                retryable=True,
                details={
                    "num_aps": len(parsed.access_points),
                    "num_walls": len(scene_dict.get("walls") or []),
                    "exc_type": type(exc).__name__,
                },
            ) from exc
        sw.mark(StageMs.RAY_TRACING.value)

        # 5) 출력 인코딩 + S3 업로드
        radio_map_dbm = sim_out["radio_map_dbm"]
        try:
            heatmap_png = encode_heatmap_png(radio_map_dbm)

            heatmap_uri = f"{output_prefix}{OutputFile.HEATMAP.value}"
            radio_uri = f"{output_prefix}{OutputFile.RADIO_MAP.value}"
            result_uri = f"{output_prefix}{OutputFile.RESULT.value}"

            upload_png(heatmap_uri, heatmap_png)
            partial[OutputFile.HEATMAP.uri_key] = heatmap_uri
            upload_npy(radio_uri, radio_map_dbm)
            partial[OutputFile.RADIO_MAP.uri_key] = radio_uri
        except Exception as exc:
            raise HandlerError(
                ErrorCode.OUTPUT_UPLOAD_FAILED,
                ErrorStage.UPLOAD_OUTPUTS,
                f"S3 PutObject failed: {exc}",
                retryable=True,
                details={"failed_uri": str(exc)[:200]},
            ) from exc
        sw.mark(StageMs.UPLOAD.value)

        # 6) result.json 작성
        stages = dict(sw.stages)
        stages[StageMs.TOTAL.value] = int((time.perf_counter() - t0) * 1000)

        radio_map_meta = {
            "grid_shape": sim_out["grid_shape"],
            "bounds_m": sim_out["bounds_m"],
            "cell_size_m": sim_out["cell_size_m"],
            "valid_cell_count": sim_out["valid_cell_count"],
            "invalid_cell_count": sim_out["invalid_cell_count"],
            "valid_ratio": sim_out["valid_ratio"],
            "rss_dbm": sim_out["rss_dbm"],
            "coverage_summary": sim_out["coverage_summary"],
        }

        result = build_result(
            parsed=parsed,
            output_prefix=output_prefix,
            started_at_iso=started_at_iso,
            stages=stages,
            radio_map_meta=radio_map_meta,
            device=device_resolved,
            engine=str(sim_out.get("engine", engine_used)),
            sionna_version=sionna_version_str(),
        )
        upload_json(result_uri, result)
        return result

    except ContractError as exc:
        failure = build_failure(
            parsed=parsed,
            started_at_iso=started_at_iso,
            code=exc.code,
            stage=ErrorStage.VALIDATE_INPUT,
            message=exc.message,
            retryable=False,
            details=exc.details,
            partial_outputs=partial,
            device=device_resolved,
            engine=engine_used,
        )
        _try_write_failure(parsed, output_prefix, failure)
        raise

    except HandlerError as exc:
        failure = build_failure(
            parsed=parsed,
            started_at_iso=started_at_iso,
            code=exc.code,
            stage=exc.stage,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
            partial_outputs=partial,
            device=device_resolved,
            engine=engine_used,
        )
        _try_write_failure(parsed, output_prefix, failure)
        raise

    except Exception as exc:
        logger.exception("unhandled error in handle_invocation")
        failure = build_failure(
            parsed=parsed,
            started_at_iso=started_at_iso,
            code=ErrorCode.INTERNAL_ERROR,
            stage=ErrorStage.UNKNOWN,
            message=str(exc) or repr(exc),
            retryable=True,
            partial_outputs=partial,
            device=device_resolved,
            engine=engine_used,
        )
        _try_write_failure(parsed, output_prefix, failure)
        raise


def _try_write_failure(
    parsed: ParsedInput | None,
    output_prefix: str | None,
    failure_payload: dict[str, Any],
) -> None:
    """failure.json 을 S3 에 쓴다. 실패해도 원본 예외를 가리지 않도록 swallow."""
    if not output_prefix:
        return
    try:
        upload_json(f"{output_prefix}{OutputFile.FAILURE.value}", failure_payload)
    except Exception:
        logger.exception("failed to upload failure.json; original error will still propagate")
