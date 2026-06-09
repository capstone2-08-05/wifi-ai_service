import logging
import os

# 앱 로거 활성화 — module-level `logger.info()` 가 콘솔에 보이도록.
# force=True: uvicorn 이 이미 root logger 에 handler 를 박았을 경우 덮어쓰기.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import AppError, ErrorCode
from app.api.routes.inference import router as inference_router
from app.api.routes.sionna import router as sionna_router
from app.infrastructure.ai_runtime.unet_gateway import preload_unet_model
from app.infrastructure.ai_runtime.yolo_gateway import preload_yolo_model
from app.infrastructure.settings import OUTPUT_DIR, preload_models

app = FastAPI(title="capstone2-ai", version="0.1.0")

# CORS — 프론트엔드(:5173) 가 /internal/sionna/images/* 등을 <img> 로 직접 로드할 때 필요.
# 또한 backend (:8000) 가 일부 endpoint 를 호출할 수도 있어 같이 허용.
# env 로 origin 커스터마이즈 가능 (콤마 구분), 기본은 dev 포트들.
_default_origins = "http://localhost:5173,http://localhost:8000"
_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inference_router)
app.include_router(sionna_router, prefix="/internal", tags=["internal"])

# 백엔드가 절대 경로를 URL로 그대로 사용하는 구조를 위한 마운트.
# 예: GET /opt/app/apps/ai_api/data/output/unet/.../wall_prob.npy
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount(str(OUTPUT_DIR), StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "error": {
                    "code": exc.code,
                    "message": exc.detail,
                    "status": exc.status_code,
                    "layer": exc.layer,
                    "phase": exc.phase,
                    "retryable": exc.retryable,
                    "context": exc.context,
                }
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": {
                    "code": ErrorCode.INTERNAL_SERVER_ERROR,
                    "message": "Internal Server Error",
                    "status": 500,
                    "layer": "api",
                    "phase": "unhandled",
                    "retryable": False,
                    "context": {},
                    "cause": {
                        "type": type(exc).__name__,
                        "detail": str(exc),
                    },
                }
            }
        },
    )


def _replace_refs(obj, old_ref: str, new_ref: str):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and value == old_ref:
                obj[key] = new_ref
            else:
                _replace_refs(value, old_ref, new_ref)
    elif isinstance(obj, list):
        for item in obj:
            _replace_refs(item, old_ref, new_ref)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    rename_map = {
        "Body_inference_unet_inference_unet_post": "UnetInferenceRequest",
        "Body_inference_yolo_inference_yolo_post": "YoloInferenceRequest",
    }
    for old_name, new_name in rename_map.items():
        if old_name in schemas and new_name not in schemas:
            schemas[new_name] = schemas.pop(old_name)
            old_ref = f"#/components/schemas/{old_name}"
            new_ref = f"#/components/schemas/{new_name}"
            _replace_refs(openapi_schema, old_ref, new_ref)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.on_event("startup")
def startup_event() -> None:
    if not preload_models():
        return
    preload_unet_model()
    preload_yolo_model()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
