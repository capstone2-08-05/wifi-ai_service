# SageMaker Async Inference custom container
# Base: PyTorch 2.1 + CUDA 11.8 runtime
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

ARG DEBIAN_FRONTEND=noninteractive

# OpenCV / Ultralytics 가 필요로 하는 system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

# --- Python deps ----------------------------------------------------------
COPY apps/sagemaker_inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- ai_runtime package (reused inference code) --------------------------
COPY packages /opt/app/packages

# --- Application source --------------------------------------------------
COPY apps/sagemaker_inference/app /opt/app/app
COPY apps/sagemaker_inference/schemas /opt/app/schemas

# --- Inference configs (baked) ------------------------------------------
COPY apps/ai_api/configs /opt/ml/configs

# --- Model weights (baked) ----------------------------------------------
# 캡스톤 규모 - 모델을 이미지에 직접 굽는 단순한 방식.
# 추후 model.tar.gz + S3 로 분리하려면 SageMaker ModelDataUrl 사용.
COPY apps/trainer/src/models/unet /opt/ml/model/unet
COPY apps/trainer/src/models/yolo /opt/ml/model/yolo

# --- Env ----------------------------------------------------------------
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
