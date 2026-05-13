"""SageMaker BYOC RF inference container 엔트리.

규격:
- GET /ping  : 200 응답 (4초 이내). 모델 로딩 완료 후만 200.
- POST /invocations : 요청 본문 = input.json. 응답 본문 = result.json. 실패 시 4xx/5xx.
"""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.constants import ErrorCode, ErrorStage, HttpStatus
from app.contracts import ContractError
from app.handler import HandlerError, handle_invocation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sagemaker_rf_inference")


app = FastAPI(title="sagemaker-rf-inference", version="0.1.0")

_READY = False


@app.on_event("startup")
def _startup() -> None:
    global _READY
    # Sionna import 만 미리 시도 — 실제 GPU 시뮬은 lazy. import 자체가 무거우면 cold start 도 길어짐.
    try:
        import sionna.rt  # noqa: F401
        _READY = True
        logger.info("startup: sionna.rt import OK — ready")
    except Exception as exc:
        # GPU 가 없거나 sionna 미설치라도 컨테이너는 살아있어야 /ping 으로 헬스체크 통과시키고
        # /invocations 호출 시 SIMULATION_FAILED 로 명확히 실패하게 한다.
        logger.warning("startup: sionna import failed (%s); container will still serve /ping", exc)
        _READY = True


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
        logger.warning("ContractError: %s — %s", exc.code.value, exc.message)
        return JSONResponse(
            status_code=HttpStatus.CONTRACT_ERROR,
            content={
                "error": {
                    "code": exc.code.value,
                    "stage": ErrorStage.VALIDATE_INPUT.value,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )
    except HandlerError as exc:
        logger.warning(
            "HandlerError: %s (stage=%s) — %s",
            exc.code.value, exc.stage.value, exc.message,
        )
        return JSONResponse(
            status_code=HttpStatus.HANDLER_ERROR,
            content={
                "error": {
                    "code": exc.code.value,
                    "stage": exc.stage.value,
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
                    "code": ErrorCode.INTERNAL_ERROR.value,
                    "stage": ErrorStage.UNKNOWN.value,
                    "message": str(exc) or repr(exc),
                    "retryable": True,
                }
            },
        )
