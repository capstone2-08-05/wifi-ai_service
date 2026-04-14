"""RF 회귀용 golden 씬/레이아웃/설정 — Sionna PoC와 공유."""

from __future__ import annotations

# 벽 없음 → path loss 중심 비교용
GOLDEN_SCENE: dict = {
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

GOLDEN_LAYOUT: dict = {
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

GOLDEN_CONFIG: dict = {
    "scene_version_id": "golden_tiny_v1",
    "grid_resolution_m": 1.0,
    "path_loss_constant_db": 40.0,
    "path_loss_exponent": 2.0,
    "include_exterior_walls": False,
    "output_dir_name": "output",
}
