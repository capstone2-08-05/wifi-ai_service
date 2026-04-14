from __future__ import annotations

from dataclasses import dataclass

from fastapi import File, Form, HTTPException, UploadFile

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class InferenceUploadRequestDto:
    file_id: str
    filename: str
    image_bytes: bytes


def _validate_image_upload(file: UploadFile) -> str:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    ext = filename.lower().rsplit(".", 1)
    ext = f".{ext[-1]}" if len(ext) > 1 else ""
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: png, jpg, jpeg",
        )
    return filename


async def parse_inference_upload_request(
    file_id: str = Form(...),
    file: UploadFile = File(...),
) -> InferenceUploadRequestDto:
    filename = _validate_image_upload(file)
    image_bytes = await file.read()
    return InferenceUploadRequestDto(
        file_id=file_id,
        filename=filename,
        image_bytes=image_bytes,
    )
