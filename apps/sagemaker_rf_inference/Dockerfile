# SageMaker Async RF Inference custom container
# Base: TensorFlow GPU runtime (Sionna RT 가 TF 기반)
#
# 빌드 context 는 rf-service/ 디렉토리. .dockerignore 는 rf-service/.dockerignore 가 적용됨.
#
# Layer 순서 원칙: 변경 빈도 낮은 것 → 높은 것 순.
#   (base) → (system libs) → (pip deps) → (configs) → (packages) → (app)

FROM tensorflow/tensorflow:2.16.1-gpu

ARG DEBIAN_FRONTEND=noninteractive

# --- 1. System libs (거의 안 바뀜) -----------------------------------------
# Mitsuba (sionna.rt 의존) 가 OpenGL/X 라이브러리 일부 요구.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

# --- 2. Python deps (requirements.txt 바뀔 때만 재실행) -----------------
COPY apps/sagemaker_rf_inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# --- 3. ai_runtime package (sionna_runtime.py 등 — 드물게 바뀜) ----------
COPY packages /opt/app/packages

# --- 4. Application source (가장 자주 바뀜) -----------------------------
COPY apps/sagemaker_rf_inference/app     /opt/app/app
COPY apps/sagemaker_rf_inference/schemas /opt/app/schemas

# --- 5. SageMaker BYOC entrypoint ---------------------------------------
# SageMaker hosting 은 컨테이너를 `docker run <image> serve` 로 띄움.
COPY apps/sagemaker_rf_inference/serve /usr/local/bin/serve
RUN sed -i 's/\r$//' /usr/local/bin/serve && chmod +x /usr/local/bin/serve

# --- Env ---------------------------------------------------------------
# NVIDIA_DRIVER_CAPABILITIES: 기본값 'compute,utility' 만으론 OptiX(ray tracing) 라이브러리가
# 컨테이너에 mount 되지 않아 Sionna RT 가 "Could not initialize OptiX!" 로 실패.
# 'graphics' 를 추가하면 NVIDIA Container Toolkit 이 libnvoptix.so 도 mount.
# MITSUBA_VARIANT: runtime.py 가 import 직후 mi.set_variant() 에 사용. GPU 가 정상이면
# cuda_ad_rgb, 실패 시 코드가 llvm_ad_rgb(CPU) 로 자동 폴백.
ENV PYTHONPATH=/opt/app \
    PYTHONUNBUFFERED=1 \
    DEFAULT_DEVICE=auto \
    CONTAINER_VERSION=rf-inference@0.1.3-debug \
    TF_CPP_MIN_LOG_LEVEL=2 \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    NVIDIA_VISIBLE_DEVICES=all \
    MITSUBA_VARIANT=cuda_ad_rgb \
    LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu

# SageMaker BYOC 는 8080 포트 표준
EXPOSE 8080

# /ping 4 초 이내 응답이 SageMaker 요구사항.
HEALTHCHECK --interval=10s --timeout=4s --start-period=180s --retries=3 \
    CMD curl -fsS http://localhost:8080/ping || exit 1

ENTRYPOINT ["serve"]
