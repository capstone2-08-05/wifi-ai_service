"""Regression tests for BaselineRfSimulator (fixed geometry, no matplotlib required for .run())."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RF_ROOT = Path(__file__).resolve().parent.parent
if str(_RF_ROOT) not in sys.path:
    sys.path.insert(0, str(_RF_ROOT))

from baseline_rf_simulator import BaselineRfSimulator  # noqa: E402
from rf_models import ApLayout, Scene, SimulationConfig  # noqa: E402

np = pytest.importorskip("numpy")


# 벽 없음 → path loss만 적용 (발표/회귀용 최소 씬)
_GOLDEN_SCENE: dict = {
    "units": "m",
    "sourceType": "golden_regression",
    "scene_version_id": "golden_tiny_v1",
    "floor_id": "floor_golden",
    "walls": [],
    "openings": [],
    "objects": [],
    "rooms": [
        {
            "id": "room_golden",
            "version_id": "golden_tiny_v1",
            "room_name": "GoldenBox",
            "space_type": "room",
            "polygon_geom": {
                "type": "Polygon",
                "coordinates": [
                    [[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0], [0.0, 0.0]]
                ],
            },
            "centroid_geom": {"type": "Point", "coordinates": [2.0, 2.0]},
            "area_m2": 16.0,
        }
    ],
}

_GOLDEN_LAYOUT: dict = {
    "scene_version_id": "golden_tiny_v1",
    "layout_name": "golden_single_ap",
    "layout_type": "regression_test",
    "aps": [
        {
            "id": "ap_001",
            "ap_name": "AP-Golden",
            "point_geom": {"type": "Point", "coordinates": [2.0, 2.0]},
            "z_m": 2.5,
            "tx_power_dbm": 20.0,
            "frequency_ghz": 5.0,
            "azimuth_deg": 0.0,
            "tilt_deg": 0.0,
        }
    ],
}

_GOLDEN_CONFIG: dict = {
    "scene_version_id": "golden_tiny_v1",
    "grid_resolution_m": 1.0,
    "path_loss_constant_db": 40.0,
    "path_loss_exponent": 2.0,
    "include_exterior_walls": False,
    "output_dir_name": "output",
}


def test_baseline_golden_rssi_metrics() -> None:
    scene = Scene.from_dict(_GOLDEN_SCENE)
    layout = ApLayout.from_dict(_GOLDEN_LAYOUT)
    config = SimulationConfig.from_dict(_GOLDEN_CONFIG)

    sim = BaselineRfSimulator(scene=scene, ap_layout=layout, config=config)
    result = sim.run()

    # 5x5 그리드, AP (2,2): 중앙 격자점은 d=min(실거리, 0.1)=0.1 → RSSI = 20 - 20 = 0
    assert result.strongest_rssi_map.shape == (5, 5)
    assert result.strongest_rssi_map[2, 2] == pytest.approx(0.0, abs=1e-9)

    # 25점 평균 RSSI (벽 없음, tx=20, PL=40+20*log10(d))
    expected_mean = -24.32659197224948
    assert result.metrics["rssi_summary"]["mean_dbm"] == pytest.approx(
        expected_mean, rel=1e-9, abs=1e-9
    )
    assert result.metrics["rssi_summary"]["max_dbm"] == pytest.approx(0.0, abs=1e-9)
    assert result.metrics["rssi_summary"]["min_dbm"] == pytest.approx(
        -29.030899869919438, rel=1e-9
    )

    cov = result.metrics["coverage_summary"]
    assert cov["fraction_rssi_ge_neg67_dbm"] == pytest.approx(1.0)
    assert cov["fraction_rssi_ge_neg70_dbm"] == pytest.approx(1.0)
    assert cov["dead_zone_fraction_lt_neg75_dbm"] == pytest.approx(0.0)


def test_ap_layout_roundtrip_to_dict() -> None:
    layout = ApLayout.from_dict(_GOLDEN_LAYOUT)
    back = ApLayout.from_dict(layout.to_dict())
    assert back.scene_version_id == layout.scene_version_id
    assert back.layout_name == layout.layout_name
    assert len(back.aps) == 1
    assert back.aps[0].position.x == pytest.approx(2.0)
    assert back.aps[0].position.y == pytest.approx(2.0)
