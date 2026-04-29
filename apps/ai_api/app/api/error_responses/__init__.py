"""OpenAPI 에러 응답 관련 공통 스키마/빌더 + 라우트별 정의 패키지."""

from __future__ import annotations

from typing import Any

ERROR_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "detail": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "status": {"type": "integer"},
                        "layer": {"type": "string"},
                        "phase": {"type": "string"},
                        "retryable": {"type": "boolean"},
                        "context": {"type": "object"},
                    },
                    "required": [
                        "code",
                        "message",
                        "status",
                        "layer",
                        "phase",
                        "retryable",
                        "context",
                    ],
                }
            },
            "required": ["error"],
        }
    },
    "required": ["detail"],
}


def make_error_example(
    *,
    code: str,
    message: str,
    status: int,
    layer: str,
    phase: str,
    context: dict[str, Any],
    retryable: bool = False,
) -> dict[str, Any]:
    """단일 error example payload(`{"detail": {"error": {...}}}`)를 만든다."""
    return {
        "detail": {
            "error": {
                "code": code,
                "message": message,
                "status": status,
                "layer": layer,
                "phase": phase,
                "retryable": retryable,
                "context": context,
            }
        }
    }


def error_response(
    *,
    description: str,
    example: dict[str, Any] | None = None,
    examples: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """FastAPI `responses=` 항목 1개를 만든다.

    - `example`: 단일 예시.
    - `examples`: `{name: {"summary": ..., "value": ...}}` 형태의 다중 예시.
    둘 중 하나만 지정한다.
    """
    if (example is None) == (examples is None):
        raise ValueError("Provide exactly one of `example` or `examples`.")

    media: dict[str, Any] = {"schema": ERROR_RESPONSE_SCHEMA}
    if example is not None:
        media["example"] = example
    else:
        media["examples"] = examples

    return {
        "description": description,
        "content": {"application/json": media},
    }


__all__ = ["ERROR_RESPONSE_SCHEMA", "make_error_example", "error_response"]
