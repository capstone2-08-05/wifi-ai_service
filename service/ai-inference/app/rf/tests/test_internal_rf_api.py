"""POST /internal/rf/run 스모크."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_internal_rf_run_sionna_dto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("httpx")
    from fastapi import FastAPI  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402

    monkeypatch.setenv("RF_STORAGE_ROOT", str(tmp_path))

    from app.routers.internal_rf import router as internal_rf_router  # noqa: E402

    app = FastAPI()
    app.include_router(internal_rf_router, prefix="/internal", tags=["internal"])
    client = TestClient(app)
    body = {
        "engine": "baseline",
        "run_type": "preview",
        "baseline": {
            "skip_heatmap": True,
            "grid_resolution_m": 0.5,
        },
        "input": {
            "kind": "sionna_dto",
            "data": {
                "config": {
                    "frequency_ghz": 5.0,
                    "tx_power_dbm": 20.0,
                    "reflection_order": 2,
                },
                "antenna": {"tx_id": "t1", "position_m": [1.0, 1.0, 2.0]},
                "scene": {
                    "scene_version": "sv_api_test",
                    "walls": [
                        {
                            "id": "w1",
                            "x1": 0.0,
                            "y1": 0.0,
                            "x2": 4.0,
                            "y2": 0.0,
                            "thickness": 0.2,
                            "height": 2.5,
                            "role": "inner",
                            "material": "wood",
                        }
                    ],
                    "openings": [],
                    "rooms": [
                        {
                            "id": "r1",
                            "points": [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
                            "center": [2.0, 2.0],
                            "area": 16.0,
                        }
                    ],
                },
            },
        },
    }
    r = client.post("/internal/rf/run", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "succeeded"
    assert data["rf_run_id"]
    assert data["metrics"]
    assert data["artifacts"]
    assert "strongest_rssi_map" in data["artifacts"]
    paths = data["paths"]
    assert paths
    assert paths["manifest"].endswith("run_manifest.json")
    assert paths["summary"].endswith("run_summary.json")
    assert paths["output_dir"]
    assert paths["heatmap"] is None  # skip_heatmap: True
