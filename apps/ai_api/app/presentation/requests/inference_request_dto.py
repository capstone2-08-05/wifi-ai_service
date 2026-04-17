from __future__ import annotations

from dataclasses import dataclass

from fastapi import File, Form, HTTPException, UploadFile
from app.api.errors import ErrorCode

_ALLOWED_EXTS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class InferenceUploadRequestDto:
    file_id: str
    filename: str
    image_bytes: bytes


def _validate_image_upload(file: UploadFile) -> str:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_REQUEST,
                    "message": "filename is required",
                    "status": 400,
                    "layer": "api",
                    "phase": "request_validate",
                    "retryable": False,
                    "context": {},
                }
            },
        )
    ext = filename.lower().rsplit(".", 1)
    ext = f".{ext[-1]}" if len(ext) > 1 else ""
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=415,
            detail={
                "error": {
                    "code": ErrorCode.UNSUPPORTED_FILE_TYPE,
                    "message": "Unsupported file type. Allowed: png, jpg, jpeg",
                    "status": 415,
                    "layer": "api",
                    "phase": "request_validate",
                    "retryable": False,
                    "context": {"extension": ext},
                }
            },
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
