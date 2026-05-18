"""Radio domain — 전파 특성, 측정면, simulation 설정, 결과."""

from app.domain.entities.radio.access_point import AccessPoint
from app.domain.entities.radio.antenna_config import AntennaConfig
from app.domain.entities.radio.correction_profile import CorrectionProfile
from app.domain.entities.radio.material import (
    DEFAULT_RADIO_MATERIALS,
    RadioMaterial,
    RadioMaterialId,
    radio_material_table,
)
from app.domain.entities.radio.measurement_plane import MeasurementPlane
from app.domain.entities.radio.resolved_sionna_config import (
    ConfigSource,
    ResolvedSionnaConfig,
)
from app.domain.entities.radio.result import RadioMapResult
from app.domain.entities.radio.scene_defaults import SceneDefaults
from app.domain.entities.radio.simulation_config import (
    PhysicalConfig,
    PropagationConfig,
    SimulationConfig,
    SolverConfig,
)
from app.domain.entities.radio.visualization_config import VisualizationConfig

__all__ = [
    "AccessPoint",
    "AntennaConfig",
    "ConfigSource",
    "CorrectionProfile",
    "DEFAULT_RADIO_MATERIALS",
    "MeasurementPlane",
    "PhysicalConfig",
    "PropagationConfig",
    "RadioMapResult",
    "RadioMaterial",
    "RadioMaterialId",
    "ResolvedSionnaConfig",
    "SceneDefaults",
    "SimulationConfig",
    "SolverConfig",
    "VisualizationConfig",
    "radio_material_table",
]
