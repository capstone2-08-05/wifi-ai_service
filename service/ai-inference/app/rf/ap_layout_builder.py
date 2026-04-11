from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from ap_candidate_generator import ApCandidate
from rf_models import AccessPoint, ApLayout, Point2D


def candidates_to_ap_layout(
    *,
    scene_version_id: str,
    layout_name: str,
    layout_type: str,
    candidates: Sequence[ApCandidate],
    ap_name_prefix: str = "AP",
    default_tx_power_dbm: float = 20.0,
    frequency_ghz: float = 5.0,
    azimuth_deg: float = 0.0,
    tilt_deg: float = 0.0,
) -> ApLayout:
    """Turn ranked AP candidates into a simulator-ready layout (at least one candidate required)."""
    if not candidates:
        raise ValueError("candidates must contain at least one ApCandidate")

    aps: list[AccessPoint] = []
    for idx, c in enumerate(candidates, start=1):
        ap_id = f"ap_{idx:03d}"
        aps.append(
            AccessPoint(
                ap_id=ap_id,
                ap_name=f"{ap_name_prefix}-{idx:02d}",
                position=Point2D(x=c.x_m, y=c.y_m),
                z_m=c.z_m,
                tx_power_dbm=default_tx_power_dbm,
                frequency_ghz=frequency_ghz,
                azimuth_deg=azimuth_deg,
                tilt_deg=tilt_deg,
            )
        )

    return ApLayout(
        scene_version_id=scene_version_id,
        layout_name=layout_name,
        layout_type=layout_type,
        aps=tuple(aps),
    )


def save_ap_layout_json(layout: ApLayout, path: Path) -> None:
    """Write layout JSON compatible with `ApLayout.from_dict`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(layout.to_dict(), ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")


def ap_candidates_to_json_rows(candidates: Sequence[ApCandidate]) -> list[dict[str, object]]:
    """Serialize candidates for `RfRunRecord.ap_candidates_json`."""
    rows: list[dict[str, object]] = []
    for c in candidates:
        rows.append(
            {
                "candidate_id": c.candidate_id,
                "room_id": c.room_id,
                "x_m": c.x_m,
                "y_m": c.y_m,
                "z_m": c.z_m,
                "candidate_type": c.candidate_type,
                "score": c.score,
                "reasons": list(c.reasons),
            }
        )
    return rows
