"""ConfigResolver — request / CorrectionProfile / app defaults 를 merge해서 ResolvedSionnaConfig 생성.

resolution 우선순위 (높음 → 낮음):
  1. request override (SionnaRunRequestDto 의 sub-config 필드)
  2. CorrectionProfile (request.correction_profile)
  3. app defaults (Pydantic Field defaults)

향후 추가 layer (현재 PR 범위 밖):
  - floor/project defaults — web-platform DB 스키마 도입 시 layer 1.5 로 추가
"""

from __future__ import annotations

from typing import Any

from app.domain.entities.radio import (
    AntennaConfig,
    ConfigSource,
    CorrectionProfile,
    PhysicalConfig,
    PropagationConfig,
    RadioMaterial,
    ResolvedSionnaConfig,
    SceneDefaults,
    SimulationConfig,
    SolverConfig,
    VisualizationConfig,
    radio_material_table,
)


def _resolve_subconfig(
    *,
    model_cls: type,
    request_override: Any,
    profile_overrides: dict[str, Any] | None,
    section_name: str,
    provenance: dict[str, ConfigSource],
) -> Any:
    """단일 sub-config 를 우선순위에 따라 merge하면서 field별 provenance 기록."""
    base = model_cls()
    base_dict = base.model_dump()
    final: dict[str, Any] = dict(base_dict)
    for key in base_dict:
        provenance[f"{section_name}.{key}"] = "app_default"

    if profile_overrides:
        for k, v in profile_overrides.items():
            if k in final:
                final[k] = v
                provenance[f"{section_name}.{k}"] = "correction_profile"

    if request_override is not None:
        # exclude_unset=True — Pydantic default 로 채워진 필드는 "사용자가 명시한 값" 이 아니므로
        # provenance 가 잘못 request 로 찍히지 않도록 한다. 클라이언트가 `{"frequency_ghz": 2.4}`
        # 만 보냈으면 다른 필드는 lower-priority layer 값을 유지.
        if hasattr(request_override, "model_dump"):
            override_dict = request_override.model_dump(exclude_unset=True)
        else:
            override_dict = dict(request_override)
        for k, v in override_dict.items():
            if k in final:
                final[k] = v
                provenance[f"{section_name}.{k}"] = "request"

    return model_cls.model_validate(final)


def _resolve_materials(
    *,
    request_materials: list[RadioMaterial] | None,
    profile: CorrectionProfile | None,
    provenance: dict[str, ConfigSource],
) -> dict[str, RadioMaterial]:
    materials = dict(radio_material_table())
    for mat_id in materials:
        provenance[f"materials.{mat_id}"] = "app_default"

    if profile and profile.materials:
        for mat_id, mat in profile.materials.items():
            materials[mat_id] = mat
            provenance[f"materials.{mat_id}"] = "correction_profile"

    if request_materials:
        for mat in request_materials:
            materials[mat.id] = mat
            provenance[f"materials.{mat.id}"] = "request"

    return materials


def resolve_sionna_config(
    *,
    simulation: SimulationConfig | None = None,
    scene_defaults: SceneDefaults | None = None,
    antenna: AntennaConfig | None = None,
    visualization: VisualizationConfig | None = None,
    materials: list[RadioMaterial] | None = None,
    correction_profile: CorrectionProfile | None = None,
) -> ResolvedSionnaConfig:
    """request 파라미터들과 (optional) CorrectionProfile 을 merge해 ResolvedSionnaConfig 반환."""
    provenance: dict[str, ConfigSource] = {}

    resolved_physical = _resolve_subconfig(
        model_cls=PhysicalConfig,
        request_override=simulation.physical if simulation else None,
        profile_overrides=correction_profile.physical_overrides if correction_profile else None,
        section_name="physical",
        provenance=provenance,
    )
    resolved_propagation = _resolve_subconfig(
        model_cls=PropagationConfig,
        request_override=simulation.propagation if simulation else None,
        profile_overrides=correction_profile.propagation_overrides if correction_profile else None,
        section_name="propagation",
        provenance=provenance,
    )
    resolved_solver = _resolve_subconfig(
        model_cls=SolverConfig,
        request_override=simulation.solver if simulation else None,
        profile_overrides=correction_profile.solver_overrides if correction_profile else None,
        section_name="solver",
        provenance=provenance,
    )
    resolved_scene_defaults = _resolve_subconfig(
        model_cls=SceneDefaults,
        request_override=scene_defaults,
        profile_overrides=correction_profile.scene_defaults_overrides if correction_profile else None,
        section_name="scene_defaults",
        provenance=provenance,
    )
    resolved_antenna = _resolve_subconfig(
        model_cls=AntennaConfig,
        request_override=antenna,
        profile_overrides=correction_profile.antenna_overrides if correction_profile else None,
        section_name="antenna",
        provenance=provenance,
    )
    resolved_visualization = _resolve_subconfig(
        model_cls=VisualizationConfig,
        request_override=visualization,
        profile_overrides=correction_profile.visualization_overrides if correction_profile else None,
        section_name="visualization",
        provenance=provenance,
    )
    resolved_materials = _resolve_materials(
        request_materials=materials,
        profile=correction_profile,
        provenance=provenance,
    )

    return ResolvedSionnaConfig(
        physical=resolved_physical,
        propagation=resolved_propagation,
        solver=resolved_solver,
        scene_defaults=resolved_scene_defaults,
        antenna=resolved_antenna,
        visualization=resolved_visualization,
        materials=resolved_materials,
        provenance=provenance,
    )
