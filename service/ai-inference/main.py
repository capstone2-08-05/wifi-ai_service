import sys
from pathlib import Path

# `app.*` 패키지 로딩(ai-inference 루트)과, 일부 레거시 스크립트용 `app/rf` flat 경로를 함께 넣는다.
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
