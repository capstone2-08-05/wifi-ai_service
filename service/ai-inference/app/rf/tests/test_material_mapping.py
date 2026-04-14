"""material_mapping / 재질 정규화 스모크."""

from __future__ import annotations

from pathlib import Path

from app.rf.materials.material_mapping import (
    get_baseline_wall_loss_db,
    map_baseline_material_to_sionna_itur,
    normalize_wall_material_key,
)
from app.rf.materials.rf_materials import MaterialProfileRegistry

_RF_ROOT = Path(__file__).resolve().parent.parent


def test_normalize_drywall_to_wood() -> None:
    assert normalize_wall_material_key("drywall") == "wood"
    assert normalize_wall_material_key("DryWall") == "wood"


def test_normalize_unknown_strings() -> None:
    assert normalize_wall_material_key("  concrete  ") == "concrete"
    assert normalize_wall_material_key("not_a_real_material") == "unknown"


def test_loss_tier_order() -> None:
    reg = MaterialProfileRegistry()
    m = reg.get_loss_db
    assert m("metal") > m("concrete") > m("glass")
    assert m("glass") > m("wood")
    assert m("wood") > m("unknown")


def test_drywall_same_loss_as_wood_after_normalize() -> None:
    assert get_baseline_wall_loss_db("drywall") == get_baseline_wall_loss_db("wood")


def test_sionna_map_enum_preserved() -> None:
    assert map_baseline_material_to_sionna_itur("wood") == "wood"
    assert map_baseline_material_to_sionna_itur("unknown") == "plasterboard"


def test_sionna_drywall_maps_via_normalize_to_wood_itu() -> None:
    assert map_baseline_material_to_sionna_itur("drywall") == "wood"


def test_material_opening_smoke_json_sionna_dto() -> None:
    import json

    from app.rf.adapters.baseline import scene_schema_to_baseline_rf_scene_dict
    from app.rf.dto.backend_scene import SionnaInputDTO
    from app.rf.models.rf_models import Scene

    path = _RF_ROOT / "sample" / "material_opening_smoke.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    dto = SionnaInputDTO.model_validate(raw)
    scene_d = scene_schema_to_baseline_rf_scene_dict(dto.scene)
    Scene.from_dict(scene_d)
