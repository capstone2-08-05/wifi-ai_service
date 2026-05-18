"""Radio domain — 전파 특성, 측정면, simulation 설정, 결과."""

from app.domain.entities.radio.access_point import AccessPoint
from app.domain.entities.radio.material import (
    DEFAULT_RADIO_MATERIALS,
    RadioMaterial,
    RadioMaterialId,
    radio_material_table,
)
from app.domain.entities.radio.measurement_plane import MeasurementPlane
from app.domain.entities.radio.result import RadioMapResult
from app.domain.entities.radio.simulation_config import (
    PhysicalConfig,
    PropagationConfig,
    SimulationConfig,
    SolverConfig,
)

__all__ = [
    "AccessPoint",
    "DEFAULT_RADIO_MATERIALS",
    "MeasurementPlane",
    "PhysicalConfig",
    "PropagationConfig",
    "RadioMapResult",
    "RadioMaterial",
    "RadioMaterialId",
    "SimulationConfig",
    "SolverConfig",
    "radio_material_table",
]
