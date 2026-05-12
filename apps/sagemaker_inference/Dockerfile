# SageMaker Async Inference custom container
# Base: PyTorch 2.1 + CUDA 11.8 runtime
#
# 빌드 context 는 rf-service/ 디렉토리. .dockerignore 는 rf-service/.dockerignore 가 적용됨.
#
# Layer 순서 원칙: 변경 빈도 낮은 것 → 높은 것 순.
#   (base) → (system libs) → (pip deps) → (configs/weights) → (app source)
# 코드만 수정 시 위쪽 layer 캐시 hit → 빌드 빨라짐.

FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

ARG DEBIAN_FRONTEND=noninteractive

# --- 1. System libs (거의 안 바뀜) -----------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

# --- 2. Python deps (requirements.txt 바뀔 때만 재실행) -----------------
COPY apps/sagemaker_inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- 3. Inference configs (거의 안 바뀜) -------------------------------
COPY apps/ai_api/configs /opt/ml/configs

# --- 4. Model weights (모델 학습 시에만 바뀜) ----------------------------
# 폴더 전체 대신 필요한 weight 파일만 굽기 — 잡파일 차단 + 캐시 안정성.
COPY apps/trainer/src/models/unet/best_unet.pth /opt/ml/model/unet/best_unet.pth
COPY apps/trainer/src/models/yolo/best.pt       /opt/ml/model/yolo/best.pt

# --- 5. ai_runtime package (드물게 바뀜) -------------------------------
COPY packages /opt/app/packages

# --- 6. Application source (가장 자주 바뀜) -----------------------------
COPY apps/sagemaker_inference/app     /opt/app/app
COPY apps/sagemaker_inference/schemas /opt/app/schemas

# --- Env ---------------------------------------------------------------
ENV PYTHONPATH=/opt/app \
    PYTHONUNBUFFERED=1 \
    UNET_CHECKPOINT_PATH=/opt/ml/model/unet/best_unet.pth \
    UNET_CONFIG_PATH=/opt/ml/configs/unet_inference.yaml \
    YOLO_MODEL_PATH=/opt/ml/model/yolo/best.pt \
    YOLO_CONFIG_PATH=/opt/ml/configs/yolo_inference.yaml \
    DEFAULT_DEVICE=auto \
    CONTAINER_VERSION=ai-inference@0.1.0

# SageMaker BYOC 는 8080 포트 표준
EXPOSE 8080

# /ping 4 초 이내 응답이 SageMaker 요구사항 — startup 시 모델 preload 완료 후 200 응답.
HEALTHCHECK --interval=10s --timeout=4s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8080/ping || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
