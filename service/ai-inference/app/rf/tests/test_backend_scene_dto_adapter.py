"""app.rf.dto → conversion.scene_to_rf_adapter → Scene / ApLayout."""

from __future__ import annotations

import pytest

from app.rf.adapters.baseline import scene_schema_to_baseline_rf_scene_dict
from app.rf.adapters.sionna import sionna_input_dto_to_engine_plan
from app.rf.dto.backend_scene import (
    AntennaDTO,
    Opening as BackendOpening,
    Room as BackendRoom,
    SceneSchema,
    SimConfigDTO,
    SionnaInputDTO,
    Wall as BackendWall,
)
from app.rf.models.rf_models import ApLayout, Scene
from app.rf.conversion.scene_to_rf_adapter import (
    antenna_dto_to_ap_layout_dict,
    sionna_input_dto_to_rf_scene_and_manual_layout,
    sionna_input_dto_to_rf_scene_dict,
    scene_schema_to_rf_scene_dict,
)


def test_scene_schema_minimal_roundtrip() -> None:
    schema = SceneSchema(
        scene_version="sv_dto_1",
        sourceType="test",
        walls=[
            BackendWall(
                id="w1",
                x1=0.0,
                y1=0.0,
                x2=4.0,
                y2=0.0,
                role="inner",
                material="wood",
            )
        ],
        openings=[
            BackendOpening(
                id="o1",
                type="door",
                x1=1.0,
                y1=0.0,
                x2=2.0,
                y2=0.0,
                wall_ref="w1",
            )
        ],
        rooms=[
            BackendRoom(
                id="r1",
                points=[[0.0, 0.0], [4.0, 0.0], [4.0, 4.0], [0.0, 4.0]],
                center=[2.0, 2.0],
                area=16.0,
            )
        ],
        objects=[],
    )
    out = scene_schema_to_baseline_rf_scene_dict(schema)
    assert scene_schema_to_rf_scene_dict(schema) == out
    scene = Scene.from_dict(out)
    assert scene.scene_version_id == "sv_dto_1"
    assert len(scene.walls) == 1
    assert scene.walls[0].material == "wood"
    assert len(scene.openings) == 1
    assert scene.openings[0].wall_id == "w1"
    assert len(scene.rooms) == 1
    assert scene.rooms[0].room_id == "r1"


def test_sionna_input_bundle_manual_ap() -> None:
    dto = SionnaInputDTO(
        config=SimConfigDTO(frequency_ghz=5.0, tx_power_dbm=20.0),
        antenna=AntennaDTO(tx_id="ap_manual", position_m=[2.0, 3.0, 2.5]),
        scene=SceneSchema(
            scene_version="sv_bundle",
            walls=[
                BackendWall(id="w1", x1=0, y1=0, x2=5, y2=0, role="outer", material="concrete")
            ],
            openings=[],
            rooms=[
                BackendRoom(
                    id="r1",
                    points=[[0, 0], [5, 0], [5, 5], [0, 5]],
                    center=[2.5, 2.5],
                    area=25.0,
                )
            ],
        ),
    )
    scene_d, layout_d = sionna_input_dto_to_rf_scene_and_manual_layout(dto)
    Scene.from_dict(scene_d)
    layout = ApLayout.from_dict(layout_d)
    assert layout.aps[0].ap_id == "ap_manual"
    assert layout.aps[0].tx_power_dbm == 20.0
    assert layout.aps[0].frequency_ghz == 5.0
    assert layout.aps[0].position.x == 2.0
    assert layout.aps[0].z_m == 2.5  # baseline bundle: z 무시 → default


def test_antenna_legacy_use_position_z() -> None:
    dto = SionnaInputDTO(
        config=SimConfigDTO(frequency_ghz=5.0, tx_power_dbm=20.0),
        antenna=AntennaDTO(tx_id="a1", position_m=[1.0, 2.0, 3.0]),
        scene=SceneSchema(
            scene_version="sv",
            walls=[BackendWall(id="w1", x1=0, y1=0, x2=1, y2=0)],
            openings=[],
            rooms=[],
        ),
    )
    scene_d = sionna_input_dto_to_rf_scene_dict(dto)
    lay = antenna_dto_to_ap_layout_dict(
        dto.antenna,
        scene_version_id=scene_d["scene_version_id"],
        sim_config=dto.config,
    )
    assert lay["aps"][0]["z_m"] == 3.0


def test_sionna_engine_plan_snapshot() -> None:
    dto = SionnaInputDTO(
        config=SimConfigDTO(frequency_ghz=5.0, tx_power_dbm=20.0, reflection_order=3),
        antenna=AntennaDTO(tx_id="tx", position_m=[1.0, 2.0, 2.5]),
        scene=SceneSchema(
            scene_version="sv_sionna",
            walls=[
                BackendWall(
                    id="w1",
                    x1=0,
                    y1=0,
                    x2=4,
                    y2=0,
                    material="wood",
                )
            ],
            openings=[],
            rooms=[],
        ),
    )
    plan = sionna_input_dto_to_engine_plan(dto, measurement_plane_z_m=1.2)
    assert plan["engine"] == "sionna_rt"
    assert plan["solver"]["max_depth"] == 3
    assert plan["solver"]["measurement_plane_z_m"] == 1.2
    assert plan["antenna"]["position_m"] == [1.0, 2.0, 2.5]
    assert plan["scene_plan"]["walls"][0]["itu_radio_material"] == "wood"


def test_sionna_input_dict_validate() -> None:
    payload = {
        "config": {"frequency_ghz": 5.0, "tx_power_dbm": 18.0, "reflection_order": 2},
        "antenna": {"tx_id": "t1", "position_m": [1.0, 1.0, 2.0]},
        "scene": {
            "scene_version": "vdict",
            "walls": [
                {
                    "id": "w1",
                    "x1": 0,
                    "y1": 0,
                    "x2": 1,
                    "y2": 0,
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
                    "points": [[0, 0], [1, 0], [1, 1], [0, 1]],
                    "center": [0.5, 0.5],
                    "area": 1.0,
                }
            ],
        },
    }
    out = sionna_input_dto_to_rf_scene_dict(payload)
    Scene.from_dict(out)


def test_opening_missing_wall_ref_errors() -> None:
    bad = SceneSchema(
        scene_version="sv_bad",
        sourceType="test",
        walls=[BackendWall(id="w1", x1=0, y1=0, x2=1, y2=0)],
        openings=[BackendOpening(id="o1", type="door", x1=0.2, y1=0, x2=0.3, y2=0, wall_ref=None)],
        rooms=[],
    )
    with pytest.raises(ValueError, match="wall_ref"):
        scene_schema_to_rf_scene_dict(bad)
