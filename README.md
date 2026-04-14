# rf-service

U-Net / YOLO 추론과 RF preview 계산을 제공하는 AI 서비스 레포입니다.

## What Lives Here

- `apps/ai_api`: 운영 FastAPI 앱
- `apps/trainer`: 모델 학습/실험 코드
- `packages/contracts`: 백엔드-서비스 공용 DTO
- `packages/ai_runtime`: 모델 런타임 모듈
- `packages/rf_core`: RF 계산 코어
- `docs`: 규약/설계 문서

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

## Quick Start

운영 API 실행은 `apps/ai_api/README.md` 기준으로 진행하세요.

```powershell
cd apps/ai_api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

상세 문서:

- 운영 API 실행/환경변수/트러블슈팅: `apps/ai_api/README.md`
- 네이밍 규칙: `docs/naming-conventions.md`

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


