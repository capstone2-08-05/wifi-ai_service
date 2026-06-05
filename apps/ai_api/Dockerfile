FROM tensorflow/tensorflow:2.16.1-gpu

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/app \
    HOST=0.0.0.0 \
    PORT=9000 \
    DEFAULT_DEVICE=auto \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics \
    NVIDIA_VISIBLE_DEVICES=all \
    MITSUBA_VARIANT=cuda_ad_mono_polarized \
    LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu

WORKDIR /opt/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/ai_api/requirements.txt /tmp/requirements.txt
COPY apps/ai_api/requirements-rf.txt /tmp/requirements-rf.txt

RUN python -m pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && pip install -r /tmp/requirements-rf.txt

COPY packages /opt/app/packages
COPY apps/ai_api /opt/app/apps/ai_api

RUN mkdir -p /opt/app/apps/ai_api/data/output

WORKDIR /opt/app/apps/ai_api

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-9000}"]
