# capstone2-ai

GPU 서버용 AI 추론 서비스입니다. U-Net 벽 분할과 YOLO 객체 탐지를 제공합니다.

## 1) 실행

```powershell
cd capstone2-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-gpu.txt   # GPU 서버인 경우
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## 2) 환경 변수

```env
YOLO_MODEL_PATH=/models/yolo.pt
UNET_CHECKPOINT_PATH=/models/unet.pt
UNET_CONFIG_PATH=./configs/unet_inference.yaml
YOLO_CONFIG_PATH=./configs/yolo_inference.yaml
YOLO_CONF_THRESHOLD=0.25
YOLO_DEVICE=cuda:0
DEFAULT_DEVICE=auto
PRELOAD_MODELS=false
```

- `UNET_CHECKPOINT_PATH`가 비어 있으면 morphology fallback 실행(확률맵 생성)
- `UNET_CONFIG_PATH`는 U-Net 서빙용 추론 설정(YAML) 경로입니다. 기본값은 `configs/unet_inference.yaml`.
- `YOLO_CONFIG_PATH`는 YOLO 서빙용 추론 설정(YAML) 경로입니다. 기본값은 `configs/yolo_inference.yaml`.
- `YOLO_MODEL_PATH`가 비어 있으면 ultralytics 기본 모델(`yolov8n.pt`) 사용
- `DEFAULT_DEVICE`는 `auto|cpu|cuda|cuda:0` 지원
- `PRELOAD_MODELS=true`면 서버 startup 시 모델 선로딩, `false`면 첫 요청 시 로딩
- 서비스는 `ai-floorplan`의 U-Net 모델/추론 유틸을 import하여 재사용합니다.

### 가중치 파일 권장 위치

- 권장 디렉터리: `service/ai-inference/models/`
  - 예: `service/ai-inference/models/unet/best_unet.pth`
  - 예: `service/ai-inference/models/yolo/best.pt`
- `.env` 예시:
  - `UNET_CHECKPOINT_PATH=./models/unet/best_unet.pth`
  - `UNET_CONFIG_PATH=./configs/unet_inference.yaml`
  - `YOLO_MODEL_PATH=./models/yolo/best.pt`
  - `YOLO_CONFIG_PATH=./configs/yolo_inference.yaml`
- 배포 시에는 보통 아래 두 방식 중 하나를 사용합니다.
  - **이미지/서버에 포함 배포**: 버전 고정이 쉽고 단순함
  - **외부 스토리지에서 주입**: 이미지 경량화, 가중치 교체가 쉬움(S3/NFS/볼륨 마운트)

## 3) API

- `GET /health`
- `POST /inference/unet`
- `POST /inference/yolo`

문서 확인:
- Swagger UI: `http://localhost:9000/docs`
- ReDoc: `http://localhost:9000/redoc`
- OpenAPI JSON: `http://localhost:9000/openapi.json`

두 추론 API 모두 `multipart/form-data`:
- `file_id`: string
- `file`: image file
- 지원 확장자: `png`, `jpg`, `jpeg`

응답:
- `/inference/unet`:
  - `output.wallProbNpyPath`: wall probability map 저장 경로 (`.npy`)
  - `output.wallProbOverlayPath`: 확률맵 heatmap을 도면 위에 입힌 overlay PNG 경로
  - `metrics`: `shape`, `dtype`, `minProb`, `maxProb`, `device`, ...
- `/inference/yolo`:
  - `output.detections`: `class_id`, `class_name`, `confidence`, `bbox[x1,y1,x2,y2]`
  - `output.previewPath`: bbox가 그려진 preview PNG 경로
  - `metrics`: `detectionCount`, `avgConfidence`, `device`, `previewPath`, ...

에러 응답:
- `400`: 파일 디코딩 실패, 빈 파일명 등 잘못된 입력
- `404`: 체크포인트 경로 등 파일 미존재
- `415`: 지원하지 않는 이미지 확장자
- `500`: 기타 서버 내부 오류

## 4) capstone2 backend 연동

`capstone2/.env`:

```env
AI_SERVICE_URL=http://<ai-host>:9000
```

backend는 업로드된 파일을 AI 서버로 직접 전송합니다.
