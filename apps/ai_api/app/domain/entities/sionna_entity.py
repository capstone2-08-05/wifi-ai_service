from __future__ import annotations

from pydantic import BaseModel


class SionnaRunPathsEntity(BaseModel):
    output_dir: str
    manifest: str
    heatmap: str | None = None
    summary: str
