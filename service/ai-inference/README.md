# capstone2-ai

GPU 서버용 AI 추론 서비스입니다. U-Net 벽 분할과 YOLO 객체 탐지를 제공합니다.

## 1) 실행

```powershell
cd capstone2-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## 2) 환경 변수

```env
YOLO_MODEL_PATH=/models/yolo.pt
UNET_CHECKPOINT_PATH=/models/unet.pt
YOLO_CONF_THRESHOLD=0.25
YOLO_DEVICE=cuda:0
```

- `UNET_CHECKPOINT_PATH`가 비어 있으면 morphology fallback 실행
- `YOLO_MODEL_PATH`가 비어 있으면 ultralytics 기본 모델(`yolov8n.pt`) 사용

## 3) API

- `GET /health`
- `POST /wall/unet`
- `POST /objects/yolo`

두 추론 API 모두 `multipart/form-data`:
- `file_id`: string
- `file`: image file

응답:
- `/wall/unet`: `maskPath`, `metrics`
- `/objects/yolo`: `detections`, `metrics`

## 4) capstone2 backend 연동

`capstone2/.env`:

```env
AI_SERVICE_URL=http://<ai-host>:9000
```

backend는 업로드된 파일을 AI 서버로 직접 전송합니다.

## 5) RF (캡스톤) — 2D floorplan 중심

- **실행·발표·Sionna:** `app/rf/RUNBOOK.md`
- **RF 입력 handoff:** `app/rf/docs/RF_SCENE_HANDOFF_SPEC.md`
- **DTO·어댑터:** `app/rf/docs/SCENE_GRAPH_ADAPTER_MAPPING.md` · `export_rf_from_backend_sample.py`
- **재질·개구·가구(preview):** `app/rf/docs/RF_MATERIAL_AND_OPENING_RULES.md`
- **비교 스크립트:** `python app/rf/compare_baseline_vs_sionna.py`
