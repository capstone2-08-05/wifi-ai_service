import logging

from fastapi import HTTPException


logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def to_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, AppError):
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    logger.exception("Unhandled exception during API request")
    return HTTPException(status_code=500, detail="Internal Server Error")
