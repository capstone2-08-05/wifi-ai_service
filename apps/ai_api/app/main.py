import sys
from pathlib import Path

# Ensure repo root is importable before loading app modules.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.routes.inference import router as inference_router
from app.api.routes.rf import router as rf_router
from app.infrastructure.settings import preload_models
from app.infrastructure.ai_runtime.unet_gateway import preload_unet_model
from app.infrastructure.ai_runtime.yolo_gateway import preload_yolo_model

# Keep ai_api importable for local scripts.
_AI_ROOT = Path(__file__).resolve().parents[1]
_AI_ROOT_STR = str(_AI_ROOT.resolve())
if _AI_ROOT_STR not in sys.path:
    sys.path.insert(0, _AI_ROOT_STR)

app = FastAPI(title="capstone2-ai", version="0.1.0")
app.include_router(inference_router)
app.include_router(rf_router, prefix="/internal", tags=["internal"])


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
