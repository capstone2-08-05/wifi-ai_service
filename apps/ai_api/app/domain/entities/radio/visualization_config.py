from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class VisualizationConfig(BaseModel):
    """Radio map 시각화 (heatmap PNG, AP marker) 설정.

    물리/시뮬레이션 의미에는 영향 없음 — 결과 PNG가 어떻게 보일지만 결정.
    """

    # AP marker
    tx_display_radius_m: float = Field(default=0.15, gt=0.0)

    # Heatmap auto-scale: percentile clipping + 너무 좁으면 mean±half_span 으로 확장
    heatmap_clip_percentile_lo: float = Field(default=5.0, ge=0.0, le=100.0)
    heatmap_clip_percentile_hi: float = Field(default=95.0, ge=0.0, le=100.0)
    heatmap_min_span_db: float = Field(default=8.0, gt=0.0)
    # valid cell 이 0개일 때 사용할 고정 범위
    heatmap_fallback_vmin_dbm: float = -90.0
    heatmap_fallback_vmax_dbm: float = -30.0

    @model_validator(mode="after")
    def _validate_percentiles(self) -> "VisualizationConfig":
        if self.heatmap_clip_percentile_lo >= self.heatmap_clip_percentile_hi:
            raise ValueError(
                "heatmap_clip_percentile_lo must be < heatmap_clip_percentile_hi"
            )
        if self.heatmap_fallback_vmin_dbm >= self.heatmap_fallback_vmax_dbm:
            raise ValueError(
                "heatmap_fallback_vmin_dbm must be < heatmap_fallback_vmax_dbm"
            )
        return self
