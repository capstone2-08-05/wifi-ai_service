import sys
from pathlib import Path

# `app/rf` 모듈들이 `backend_scene_dto`, `adapter_baseline_dto` 등 flat 이름으로 import 하므로
# 서비스 루트와 `app/rf` 를 path 에 넣는다.
_AI_ROOT = Path(__file__).resolve().parent
_RF_ROOT = _AI_ROOT / "app" / "rf"
for _p in (_AI_ROOT, _RF_ROOT):
    _s = str(_p.resolve())
    if _s not in sys.path:
        sys.path.insert(0, _s)

from fastapi import FastAPI

from app.routers.inference import router as inference_router
from app.routers.internal_rf import router as internal_rf_router

app = FastAPI(title="capstone2-ai", version="0.1.0")
app.include_router(inference_router)
app.include_router(internal_rf_router, prefix="/internal", tags=["internal"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
