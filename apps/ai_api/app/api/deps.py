"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import File, Form, UploadFile

from app.api.errors import AppError, ErrorCode
from app.presentation.requests.inference_request_dto import InferenceUploadRequestDto

_ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _validate_image_upload(file: UploadFile) -> str:
    filename = (file.filename or "").strip()
    if not filename:
        raise AppError(
            status_code=400,
            detail="filename is required",
            code=ErrorCode.INVALID_REQUEST,
            layer="api",
            phase="request_validate",
            retryable=False,
            context={},
        )
    parts = filename.lower().rsplit(".", 1)
    ext = f".{parts[-1]}" if len(parts) > 1 else ""
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise AppError(
            status_code=415,
            detail="Unsupported file type. Allowed: png, jpg, jpeg",
            code=ErrorCode.UNSUPPORTED_FILE_TYPE,
            layer="api",
            phase="request_validate",
            retryable=False,
            context={"extension": ext},
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
