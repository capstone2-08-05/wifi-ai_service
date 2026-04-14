# ai_api

`rf-service` 내 운영 FastAPI 앱입니다.  
U-Net/YOLO 추론과 RF preview API를 제공합니다.

## Architecture (Current)

```text
app/
├─ api/routes              # endpoint
├─ presentation            # RequestDto / ResponseDto
├─ usecases                # usecase orchestration
├─ infrastructure          # runtime/rf adapters
└─ main.py
```

실행 흐름:

- `api/routes` -> `usecases` -> `infrastructure` -> `packages/*`

## Run

아래 순서대로 하면 `ai_api` 실행에 필요한 항목을 모두 준비할 수 있습니다.

### 1) 환경 준비

```powershell
cd rf-service/apps/ai_api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

GPU 추론이 필요하면 추가 설치:

```powershell
pip install -r requirements-gpu.txt
```

### 2) 가중치 파일 위치

기본 `.env` 기준 권장 위치:

- U-Net checkpoint: `apps/trainer/src/models/unet/best_unet.pth`
- YOLO weights: `apps/trainer/src/models/yolo/best.pt`

예시:

```text
apps/trainer/src/models/
  unet/best_unet.pth
  yolo/best.pt
```

파일명이 다르면 `.env`에서 아래 두 값만 수정하면 됩니다.

- `UNET_CHECKPOINT_PATH`
- `YOLO_MODEL_PATH`

### 3) 실행

```powershell
cd rf-service/apps/ai_api
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

## Environment Variables

주요 항목:

- `UNET_CHECKPOINT_PATH`: U-Net 가중치 파일 경로
- `UNET_CONFIG_PATH`: U-Net 추론 설정 YAML 경로
- `YOLO_MODEL_PATH`: YOLO 가중치 파일 경로
- `YOLO_CONFIG_PATH`: YOLO 추론 설정 YAML 경로
- `YOLO_CONF_THRESHOLD`: YOLO confidence threshold
- `YOLO_DEVICE`: YOLO 디바이스 강제 지정(예: `cpu`, `cuda:0`)
- `DEFAULT_DEVICE`: 기본 디바이스(`auto|cpu|cuda`)
- `PRELOAD_MODELS`: 시작 시 모델 preload 여부(`true|false`)
- `RF_ARTIFACT_IMAGE_URL_TEMPLATE`: RF 결과 `imageUrl` 템플릿 (`{rf_run_id}` 사용)

### Common Startup Issues

- `No module named 'app'`
  - `apps/ai_api`에서 실행해야 함
  - 실행 커맨드는 `uvicorn app.main:app ...`
- `No module named 'packages'`
  - `app.main`의 repo root path bootstrap이 적용된 최신 코드인지 확인
  - 레포 루트가 `c:/capstone2/rf-service`인지 확인
- `Form data requires "python-multipart"`
  - `pip install -r requirements.txt` 재실행 (또는 `pip install python-multipart`)

## API

- `GET /health`
- `POST /inference/unet`
- `POST /inference/yolo`
- `POST /internal/rf/run`
- `POST /internal/rf/sionna/poc` (PoC: SionnaRT engine plan 생성)

문서:

- Swagger: `http://localhost:9000/docs`
- OpenAPI: `http://localhost:9000/openapi.json`

## Input/Output Notes

- `/inference/*`는 `multipart/form-data`:
  - `file_id`
  - `file` (`png|jpg|jpeg`)
- `/internal/rf/run` 응답은 `imageUrl`(템플릿 기반 URL) 포함
- `/internal/rf/sionna/poc`는 SionnaRT 실행 전 단계의 엔진 입력 plan 스냅샷을 반환

## Backend Integration

`web-platform`(backend)에서 아래 값으로 호출:

```env
AI_SERVICE_URL=http://<ai-host>:9000
```
