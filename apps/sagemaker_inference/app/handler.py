"""SageMaker /invocations 한 번의 처리 오케스트레이션.

input.json → S3 다운로드 → U-Net + YOLO 추론 → 출력 5종 S3 PUT.
실패 시 failure.json 을 S3 PUT 하고 ContractError/HandlerError 로 raise.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import cv2
import numpy as np

from app.constants import (
    DEFAULT_UNET_THRESHOLD,
    DEFAULT_YOLO_CONF_THRESHOLD,
    ErrorCode,
    ErrorStage,
    OutputFile,
    StageMs,
)
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
from app.postprocess import (
    build_detections_payload,
    encode_preview_overlay_png,
    encode_wall_mask_png,
)
from app.runtime import (
    default_device,
    get_yolo_config,
    resolve_device,
    unet_checkpoint_path,
    unet_config_path,
    yolo_weights_path,
)
from app.s3_io import download_bytes, upload_json, upload_npy, upload_png
from packages.ai_runtime.unet_runtime import run_unet_probability_inference
from packages.ai_runtime.yolo_runtime import run_yolo_inference_result

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


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise HandlerError(
            ErrorCode.SOURCE_IMAGE_DECODE_FAILED,
            ErrorStage.DECODE_IMAGE,
            "cv2.imdecode returned None; not a valid image",
            retryable=False,
            details={"downloaded_bytes": len(image_bytes), "head_hex": image_bytes[:16].hex()},
        )
    return img


def _yolo_detections(
    image_bgr: np.ndarray, conf_threshold: float
) -> tuple[list[dict[str, Any]], str, str]:
    model, result, device = run_yolo_inference_result(
        image_bgr,
        weights_path=yolo_weights_path(),
        conf_threshold=conf_threshold,
        preferred_device="",
        default_device=default_device(),
    )
    detections: list[dict[str, Any]] = []
    if result.boxes is not None:
        names = model.names if isinstance(model.names, dict) else {}
        for box in result.boxes:
            cls_id = int(box.cls.item())
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append(
                {
                    "class_id": cls_id,
                    "class_name": names.get(cls_id, str(cls_id)),
                    "confidence": round(float(box.conf.item()), 4),
                    "bbox": [x1, y1, x2, y2],
                }
            )
    return detections, yolo_weights_path(), device


def handle_invocation(payload_bytes: bytes) -> dict[str, Any]:
    """SageMaker /invocations 한 번 처리. 성공 시 result.json dict 반환."""
    t0 = time.perf_counter()
    started_at_iso = _now_iso()
    parsed: ParsedInput | None = None
    output_prefix: str | None = None
    partial: dict[str, str] = {}
    device_resolved = resolve_device(default_device())

    try:
        # 1) 입력 검증
        parsed = parse_input(payload_bytes)
        output_prefix = normalize_output_prefix(parsed.output_prefix)

        sw = Stopwatch()

        # 2) 원본 이미지 다운로드
        try:
            image_bytes = download_bytes(parsed.source_image_s3_uri)
        except Exception as exc:
            raise HandlerError(
                ErrorCode.SOURCE_IMAGE_DOWNLOAD_FAILED,
                ErrorStage.DOWNLOAD_SOURCE,
                f"S3 GetObject failed: {exc}",
                retryable=True,
                details={"source_image_s3_uri": parsed.source_image_s3_uri},
            ) from exc
        sw.mark(StageMs.DOWNLOAD.value)

        # 3) 이미지 디코드
        image_bgr = _decode_bgr(image_bytes)
        height_px, width_px = image_bgr.shape[:2]

        # 4) U-Net 추론
        unet_threshold = float(parsed.options.get("unet_threshold", DEFAULT_UNET_THRESHOLD))
        if parsed.tasks.get("wall_segmentation", True):
            try:
                prob_map, unet_rt = run_unet_probability_inference(
                    image_bgr,
                    config_path=unet_config_path(),
                    checkpoint_path=unet_checkpoint_path(),
                    default_device=default_device(),
                )
                prob_map = prob_map.astype(np.float32, copy=False)
            except Exception as exc:
                raise HandlerError(
                    ErrorCode.UNET_INFERENCE_FAILED,
                    ErrorStage.WALL_SEGMENTATION,
                    f"U-Net inference failed: {exc}",
                    retryable=True,
                ) from exc
        else:
            prob_map = np.zeros((height_px, width_px), dtype=np.float32)
            unet_rt = {"model": "skipped", "device": device_resolved, "mode": "skipped"}
        sw.mark(StageMs.UNET.value)

        # 5) YOLO 추론
        yolo_conf = float(
            parsed.options.get("yolo_conf_threshold")
            or get_yolo_config().get("infer", {}).get("conf_threshold", DEFAULT_YOLO_CONF_THRESHOLD)
        )
        if parsed.tasks.get("object_detection", True):
            try:
                detections, yolo_model_used, yolo_device = _yolo_detections(image_bgr, yolo_conf)
            except Exception as exc:
                raise HandlerError(
                    ErrorCode.YOLO_INFERENCE_FAILED,
                    ErrorStage.OBJECT_DETECTION,
                    f"YOLO inference failed: {exc}",
                    retryable=True,
                ) from exc
        else:
            detections = []
            yolo_model_used = "skipped"
            yolo_device = device_resolved
        sw.mark(StageMs.YOLO.value)

        # 6) 출력 인코딩 + S3 업로드
        try:
            mask_png = encode_wall_mask_png(prob_map, threshold=unet_threshold)
            overlay_png = encode_preview_overlay_png(image_bgr, prob_map, detections)
            detections_payload = build_detections_payload(
                detections,
                image_size=(width_px, height_px),
                model_name=yolo_model_used,
                threshold=yolo_conf,
                device=yolo_device,
            )

            mask_uri = f"{output_prefix}{OutputFile.WALL_MASK.value}"
            prob_uri = f"{output_prefix}{OutputFile.WALL_PROB_MAP.value}"
            det_uri = f"{output_prefix}{OutputFile.DETECTIONS.value}"
            overlay_uri = f"{output_prefix}{OutputFile.PREVIEW_OVERLAY.value}"
            result_uri = f"{output_prefix}{OutputFile.RESULT.value}"

            upload_png(mask_uri, mask_png)
            partial[OutputFile.WALL_MASK.uri_key] = mask_uri
            upload_npy(prob_uri, prob_map)
            partial[OutputFile.WALL_PROB_MAP.uri_key] = prob_uri
            upload_json(det_uri, detections_payload)
            partial[OutputFile.DETECTIONS.uri_key] = det_uri
            upload_png(overlay_uri, overlay_png)
        except Exception as exc:
            raise HandlerError(
                ErrorCode.OUTPUT_UPLOAD_FAILED,
                ErrorStage.UPLOAD_OUTPUTS,
                f"S3 PutObject failed: {exc}",
                retryable=True,
                details={"failed_uri": str(exc)[:200]},
            ) from exc
        sw.mark(StageMs.UPLOAD.value)

        # 7) result.json 작성
        stages = dict(sw.stages)
        stages[StageMs.TOTAL.value] = int((time.perf_counter() - t0) * 1000)
        result = build_result(
            parsed=parsed,
            output_prefix=output_prefix,
            started_at_iso=started_at_iso,
            stages=stages,
            image_size=(width_px, height_px),
            device=yolo_device or unet_rt.get("device", device_resolved),
            unet_model=str(unet_rt.get("model", "")) or None,
            yolo_model=yolo_model_used,
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
