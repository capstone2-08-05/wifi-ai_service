"""contracts.py 단위 테스트 — input 검증, failure/result 빌더."""
from __future__ import annotations

import json

import pytest

from app.constants import SCHEMA_VERSION, ErrorCode, ErrorStage
from app.contracts import (
    ContractError,
    build_failure,
    build_result,
    normalize_output_prefix,
    parse_input,
)


def _valid_input() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": "test-job-001",
        "source_image_s3_uri": "s3://my-bucket/projects/p1/source.png",
        "output_prefix": "s3://my-bucket/ai-jobs/test-job-001/output/",
        "tasks": {"wall_segmentation": True, "object_detection": True},
    }


def test_parse_input_happy_path():
    parsed = parse_input(json.dumps(_valid_input()).encode("utf-8"))
    assert parsed.job_id == "test-job-001"
    assert parsed.tasks == {"wall_segmentation": True, "object_detection": True}
    assert parsed.output_prefix.endswith("/")


def test_parse_input_invalid_json_raises():
    with pytest.raises(ContractError) as ei:
        parse_input(b"not-json")
    assert ei.value.code == ErrorCode.INVALID_INPUT


def test_parse_input_wrong_schema_version_raises():
    body = _valid_input()
    body["schema_version"] = "9.9"
    with pytest.raises(ContractError) as ei:
        parse_input(json.dumps(body).encode("utf-8"))
    assert ei.value.code == ErrorCode.UNSUPPORTED_SCHEMA_VERSION


def test_parse_input_missing_required_field_raises():
    body = _valid_input()
    body.pop("output_prefix")
    with pytest.raises(ContractError) as ei:
        parse_input(json.dumps(body).encode("utf-8"))
    assert ei.value.code == ErrorCode.INVALID_INPUT


def test_parse_input_rejects_unknown_field():
    body = _valid_input()
    body["mystery"] = "x"
    with pytest.raises(ContractError):
        parse_input(json.dumps(body).encode("utf-8"))


def test_normalize_output_prefix():
    assert normalize_output_prefix("s3://b/p") == "s3://b/p/"
    assert normalize_output_prefix("s3://b/p/") == "s3://b/p/"


def test_build_result_shape():
    parsed = parse_input(json.dumps(_valid_input()).encode("utf-8"))
    result = build_result(
        parsed=parsed,
        output_prefix=parsed.output_prefix,
        started_at_iso="2026-05-12T03:21:08.421Z",
        stages={"download_ms": 100, "unet_ms": 200, "yolo_ms": 50, "upload_ms": 30, "total_ms": 380},
        image_size=(1600, 1200),
        device="cuda:0",
        unet_model="unet-checkpoint",
        yolo_model="yolov8n-best",
    )
    assert result["status"] == "completed"
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["outputs"]["wall_mask_s3_uri"].endswith("wall_mask.png")
    assert result["outputs"]["wall_prob_map_s3_uri"].endswith("wall_prob_map.npy")
    assert result["image"]["width_px"] == 1600
    assert "scene_draft_s3_uri" not in result["outputs"]  # 책임 분리: 컨테이너 출력 아님


def test_build_failure_shape_with_parsed_input():
    parsed = parse_input(json.dumps(_valid_input()).encode("utf-8"))
    failure = build_failure(
        parsed=parsed,
        started_at_iso="2026-05-12T03:21:08.421Z",
        code=ErrorCode.SOURCE_IMAGE_DECODE_FAILED,
        stage=ErrorStage.DECODE_IMAGE,
        message="bad image",
        retryable=False,
        details={"head_hex": "deadbeef"},
        device="cuda:0",
    )
    assert failure["status"] == "failed"
    assert failure["error"]["code"] == ErrorCode.SOURCE_IMAGE_DECODE_FAILED
    assert failure["job_id"] == parsed.job_id


def test_build_failure_without_parsed_input():
    """input 파싱 자체가 실패한 케이스 — parsed=None 이어도 fail 안 함."""
    failure = build_failure(
        parsed=None,
        started_at_iso=None,
        code=ErrorCode.INVALID_INPUT,
        stage=ErrorStage.VALIDATE_INPUT,
        message="bad json",
    )
    assert failure["status"] == "failed"
    assert failure["job_id"] == "unknown"
    assert "started_at" not in failure
