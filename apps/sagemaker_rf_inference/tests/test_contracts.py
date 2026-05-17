"""contracts.py unit tests — Sionna 의존성 없이 돌아간다."""
from __future__ import annotations

import json

import pytest

from app.constants import ErrorCode
from app.contracts import (
    ContractError,
    build_failure,
    build_result,
    normalize_output_prefix,
    parse_input,
)


def _good_payload() -> dict:
    return {
        "schema_version": "1.0",
        "job_id": "rf-job-abc",
        "project_id": "proj-1",
        "floor_id": "floor-1",
        "scene_s3_uri": "s3://my-bucket/scenes/abc/scene.json",
        "output_prefix": "s3://my-bucket/rf-jobs/rf-job-abc/output/",
        "simulation": {
            "frequency_hz": 5200000000,
            "tx_power_dbm": 20,
            "resolution_m": 0.5,
        },
        "access_points": [
            {"id": "ap-1", "x_m": 3.2, "y_m": 4.1, "z_m": 1.2},
        ],
        "metadata": {"trace_id": "abc"},
    }


def test_parse_input_ok():
    payload = _good_payload()
    parsed = parse_input(json.dumps(payload).encode("utf-8"))

    assert parsed.job_id == "rf-job-abc"
    assert parsed.scene_s3_uri == "s3://my-bucket/scenes/abc/scene.json"
    assert parsed.simulation.frequency_hz == 5200000000
    assert parsed.simulation.tx_power_dbm == 20
    assert parsed.simulation.resolution_m == 0.5
    assert parsed.simulation.max_depth == 3  # default
    assert parsed.simulation.samples_per_tx == 100_000  # default
    assert len(parsed.access_points) == 1
    assert parsed.access_points[0].id == "ap-1"
    assert parsed.metadata == {"trace_id": "abc"}


def test_parse_input_bad_json():
    with pytest.raises(ContractError) as exc:
        parse_input(b"not a json")
    assert exc.value.code == ErrorCode.INVALID_INPUT


def test_parse_input_wrong_schema_version():
    payload = _good_payload()
    payload["schema_version"] = "0.9"
    with pytest.raises(ContractError) as exc:
        parse_input(json.dumps(payload).encode("utf-8"))
    assert exc.value.code == ErrorCode.UNSUPPORTED_SCHEMA_VERSION


def test_parse_input_missing_ap():
    payload = _good_payload()
    payload["access_points"] = []
    with pytest.raises(ContractError) as exc:
        parse_input(json.dumps(payload).encode("utf-8"))
    assert exc.value.code == ErrorCode.INVALID_INPUT


def test_parse_input_bad_output_prefix():
    payload = _good_payload()
    payload["output_prefix"] = "s3://my-bucket/no-trailing-slash"
    with pytest.raises(ContractError) as exc:
        parse_input(json.dumps(payload).encode("utf-8"))
    assert exc.value.code == ErrorCode.INVALID_INPUT


def test_normalize_output_prefix():
    assert normalize_output_prefix("s3://b/p/") == "s3://b/p/"
    assert normalize_output_prefix("s3://b/p") == "s3://b/p/"


def test_build_result_shape():
    parsed = parse_input(json.dumps(_good_payload()).encode("utf-8"))
    result = build_result(
        parsed=parsed,
        output_prefix="s3://my-bucket/rf-jobs/rf-job-abc/output/",
        started_at_iso="2026-05-13T12:00:00.000Z",
        stages={"download_scene_ms": 100, "ray_tracing_ms": 5000, "total_ms": 5200},
        radio_map_meta={
            "grid_shape": [40, 60],
            "bounds_m": {"min_x": 0, "max_x": 20, "min_y": 0, "max_y": 30, "z": 1.0},
            "cell_size_m": 0.5,
            "valid_cell_count": 2400,
            "invalid_cell_count": 0,
            "valid_ratio": 1.0,
            "rss_dbm": {"min": -90, "max": -40, "mean": -65},
            "coverage_summary": {"ge_-67": 0.5, "ge_-70": 0.6, "ge_-75": 0.7},
        },
        device="cuda:0",
        engine="sionna_rt",
        sionna_version="1.0.2",
    )
    assert result["status"] == "completed"
    assert result["job_id"] == "rf-job-abc"
    assert result["outputs"]["result_s3_uri"].endswith("/result.json")
    assert result["outputs"]["heatmap_s3_uri"].endswith("/heatmap.png")
    assert result["outputs"]["radio_map_s3_uri"].endswith("/radio_map.npy")
    assert result["echo"] == {"trace_id": "abc"}
    assert result["runtime"]["sionna_version"] == "1.0.2"


def test_build_failure_with_partial():
    parsed = parse_input(json.dumps(_good_payload()).encode("utf-8"))
    failure = build_failure(
        parsed=parsed,
        started_at_iso="2026-05-13T12:00:00.000Z",
        code=ErrorCode.SIMULATION_FAILED,
        stage=__import__("app.constants", fromlist=["ErrorStage"]).ErrorStage.RAY_TRACING,
        message="GPU OOM",
        retryable=True,
        partial_outputs={"heatmap_s3_uri": "s3://b/p/heatmap.png"},
        device="cuda:0",
        engine="sionna_rt",
    )
    assert failure["status"] == "failed"
    assert failure["error"]["code"] == "SIMULATION_FAILED"
    assert failure["error"]["retryable"] is True
    assert failure["partial_outputs"] == {"heatmap_s3_uri": "s3://b/p/heatmap.png"}
