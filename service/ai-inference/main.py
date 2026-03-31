from fastapi import FastAPI

from app.routers.inference import router as inference_router

app = FastAPI(title="capstone2-ai", version="0.1.0")
app.include_router(inference_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
