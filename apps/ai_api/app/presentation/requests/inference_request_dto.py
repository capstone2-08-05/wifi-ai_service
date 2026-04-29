from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceUploadRequestDto:
    file_id: str
    filename: str
    image_bytes: bytes
