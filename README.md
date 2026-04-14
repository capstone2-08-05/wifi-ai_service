# ai-service (rf-service)

AI 추론(U-Net/YOLO)과 RF preview 계산을 제공하는 서비스 레포입니다.

## Overall Architecture

```text
apps/ai_api (FastAPI)
  -> api/routes
  -> usecases
  -> infrastructure
  -> packages/ai_runtime + packages/rf_core
  -> response dto 반환
```

레이어 흐름:

- `api/routes`: HTTP endpoint
- `presentation/requests|responses`: API 입출력 DTO
- `usecases`: 유즈케이스 오케스트레이션
- `infrastructure`: 런타임/코어 호출 어댑터
- `packages/*`: 재사용 가능한 실제 계산 로직

## Repository Structure

- `apps/ai_api`
  - 운영 FastAPI 앱
  - 엔드포인트: `/inference/unet`, `/inference/yolo`, `/internal/rf/run`, `/internal/rf/sionna/poc`
- `apps/trainer`
  - 학습/추론 스크립트 (모델 개발용)
- `packages/contracts`
  - 공용 스키마/DTO
- `packages/ai_runtime`
  - U-Net/YOLO 런타임 실행 모듈
- `packages/rf_core`
  - RF 도메인 계산 코어
  - adapter/conversion/model/simulation/persistence 포함
- `docs`
  - 개발 규약 문서
  - 네이밍 규칙: `docs/naming-conventions.md`
- `docker`
  - 배포 관련 설정

## Run (Local)

아래 순서대로 하면 `ai_api` 실행에 필요한 항목을 모두 준비할 수 있습니다.

### 1) 환경 준비

```powershell
cd apps/ai_api
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
cd apps/ai_api
.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

문서 확인:

- Swagger: `http://localhost:9000/docs`
- OpenAPI: `http://localhost:9000/openapi.json`
- Health: `http://localhost:9000/health`

## Environment Variables

`apps/ai_api/.env` 주요 값:

- `UNET_CHECKPOINT_PATH`: U-Net 가중치 파일 경로
- `UNET_CONFIG_PATH`: U-Net 추론 설정 YAML 경로
- `YOLO_MODEL_PATH`: YOLO 가중치 파일 경로
- `YOLO_CONFIG_PATH`: YOLO 추론 설정 YAML 경로
- `YOLO_CONF_THRESHOLD`: YOLO confidence threshold
- `YOLO_DEVICE`: YOLO 디바이스 강제 지정(예: `cpu`, `cuda:0`)
- `DEFAULT_DEVICE`: 기본 디바이스(`auto|cpu|cuda`)
- `PRELOAD_MODELS`: 시작 시 모델 preload 여부(`true|false`)
- `RF_ARTIFACT_IMAGE_URL_TEMPLATE`:
  - RF 응답의 `imageUrl` 템플릿 (`{rf_run_id}` placeholder 사용)
  - 추후 S3 전환 시 이 값만 변경하면 됨

### Common Startup Issues

- `No module named 'app'`
  - `apps/ai_api`에서 실행해야 함
  - 실행 커맨드는 `uvicorn app.main:app ...`
- `No module named 'packages'`
  - `app.main`의 repo root path bootstrap이 적용된 최신 코드인지 확인
  - 레포 루트가 `c:/capstone2/rf-service`인지 확인
- `Form data requires "python-multipart"`
  - `pip install -r requirements.txt` 재실행 (또는 `pip install python-multipart`)

## Dependency Notes

운영 API 실행에 필요한 것은 기본적으로 아래 2개입니다.

- `apps/ai_api/requirements.txt` (필수)
- `apps/ai_api/requirements-gpu.txt` (GPU 사용 시)

아래 파일들은 용도가 다릅니다.

- `apps/trainer/requirements*.txt`
  - 모델 학습/실험용(운영 API 필수 아님)
- `packages/rf_core/requirements-rf-lock.txt`
  - RF 재현/검증용 고정 버전 참고 파일(운영 API 필수 아님)

## RF Terms (FAQ)

### 1) persistence는 무엇인가?

`packages/rf_core/persistence/rf_persistence.py`는 RF 실행 이력/산출물 메타데이터 저장용 프로토타입 레이어입니다.

- 파일 기반(JSON) 저장:
  - `rf_runs.json`
  - `ap_layouts.json`
  - `rf_maps.json`

즉 계산 엔진이 아니라 실행 기록 저장소입니다.

### 2) 왜 스키마가 따로 있는가?

`packages/rf_core/schemas/backend_scene_schema.json`은 백엔드 handoff payload 계약(JSON Schema)입니다.

- 코드 타입(Pydantic/dataclass)과 별개로
- 시스템 간 인터페이스 계약을 명시/검증하기 위해 분리합니다.

### 3) golden fixture는 무엇인가?

`packages/rf_core/fixtures/golden_fixtures.py`는 회귀 테스트용 기준 입력 데이터입니다.

- 운영 데이터가 아니라 테스트 기준점
- 코드 변경 후 결과 일관성 확인용

## Error Handling Pattern

API 라우터는 공통 예외 매퍼를 사용합니다.

- 위치: `apps/ai_api/app/api/errors.py`
- 패턴:
  - 라우터에서 `try/except Exception`
  - `to_http_exception()`으로 변환
  - 비즈니스 예외는 `AppError(status_code, detail)`로 명시 가능


