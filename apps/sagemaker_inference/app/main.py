"""SageMaker BYOC inference container 엔트리.

규격:
- GET /ping  : 200 응답 (4초 이내). 모델 로딩 완료 후만 200.
- POST /invocations : 요청 본문 = input.json. 응답 본문 = result.json. 실패 시 5xx.
"""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.constants import ErrorCode, ErrorStage, HttpStatus
from app.contracts import ContractError
from app.handler import HandlerError, handle_invocation
from app.runtime import preload_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sagemaker_inference")


app = FastAPI(title="sagemaker-inference", version="0.1.0")

_READY = False


@app.on_event("startup")
def _startup() -> None:
    global _READY
    info = preload_all()
    unet_ok = info.get("unet", {}).get("loaded", False)
    yolo_ok = info.get("yolo", {}).get("loaded", False)
    _READY = unet_ok and yolo_ok
    if not _READY:
        logger.error("startup: not ready — unet=%s yolo=%s", unet_ok, yolo_ok)
    else:
        logger.info("startup: ready (device=%s)", info.get("device"))


@app.get("/ping")
def ping() -> Response:
    if not _READY:
        return Response(status_code=HttpStatus.NOT_READY)
    return Response(status_code=HttpStatus.READY)


@app.post("/invocations")
async def invocations(request: Request) -> JSONResponse:
    body = await request.body()
    try:
        result = handle_invocation(body)
        return JSONResponse(content=result, status_code=HttpStatus.OK)
    except ContractError as exc:
        logger.warning("ContractError: %s — %s", exc.code, exc.message)
        return JSONResponse(
            status_code=HttpStatus.CONTRACT_ERROR,
            content={
                "error": {
                    "code": str(exc.code),
                    "stage": str(ErrorStage.VALIDATE_INPUT),
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
    except HandlerError as exc:
        logger.warning("HandlerError: %s (stage=%s) — %s", exc.code, exc.stage, exc.message)
        # SageMaker 가 FailureLocation 에 쓸 수 있도록 5xx 로 응답.
        # 컨테이너는 이미 output_prefix/failure.json 도 PUT 했음 (handler 내부).
        return JSONResponse(
            status_code=HttpStatus.HANDLER_ERROR,
            content={
                "error": {
                    "code": str(exc.code),
                    "stage": str(exc.stage),
                    "message": exc.message,
                    "retryable": exc.retryable,
                    "details": exc.details,
                }
            },
        )
    except Exception as exc:
        logger.exception("unhandled exception in /invocations")
        return JSONResponse(
            status_code=HttpStatus.INTERNAL_ERROR,
            content={
                "error": {
                    "code": str(ErrorCode.INTERNAL_ERROR),
                    "stage": str(ErrorStage.UNKNOWN),
                    "message": str(exc) or repr(exc),
                    "retryable": True,
                }
            },
        )
