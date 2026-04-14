# Naming Conventions

`rf-service` 코드 네이밍 규칙입니다.  
현재 기준은 `apps/ai_api/app` 레이어드 아키텍처를 우선으로 합니다.

## Core Rules

- **DTO 클래스**: `*RequestDto`, `*ResponseDto`
- **Entity 클래스**: `*Entity`
- **Usecase 파일**: `*_usecase.py`
- **Usecase 함수**: `*_usecase`
- **라우터 파일**: 리소스 중심 (`inference.py`, `rf.py`)
- **인프라 실행기 파일**: 역할 중심 (`*_runner.py`, `*_gateway.py`)

## Layer Rules

- `api/routes`
  - FastAPI endpoint 정의만 둡니다.
  - 파일명은 도메인 리소스 기준으로 짧게 유지합니다.
  - 비즈니스 로직/변환 로직은 넣지 않습니다.

- `presentation/requests`
  - API 입력 DTO만 둡니다.
  - 파일명: `*_request_dto.py`
  - 예: `rf_request_dto.py`, `inference_request_dto.py`

- `presentation/responses`
  - API 출력 DTO + response builder만 둡니다.
  - 파일명: `*_response_dto.py`
  - 예: `rf_response_dto.py`, `inference_response_dto.py`

- `domain/entities`
  - 도메인 모델만 둡니다.
  - 파일명: `*_entity.py`
  - 클래스명: `*Entity`

- `usecases`
  - 유즈케이스 오케스트레이션만 둡니다.
  - 파일명: `*_usecase.py`
  - 함수명: `*_usecase`

- `infrastructure`
  - 외부 라이브러리/패키지 호출 어댑터를 둡니다.
  - `ai_runtime`: 모델 런타임 호출
  - `rf`: RF 코어 호출
  - 파일명은 `*_runner.py`, `*_gateway.py`를 사용합니다.

## Naming Examples

- Request DTO: `RfRunRequestDto`, `InferenceUploadRequestDto`
- Response DTO: `RfRunResponseDto`
- Entity: `RfRunPathsEntity`, `BaselineParamsEntity`
- Usecase function: `run_rf_preview_usecase`, `run_unet_usecase`

## Prohibited Patterns

- DTO에 `Entity` 접미사 사용 금지
- Entity에 `Dto` 접미사 사용 금지
- 라우터 파일에 `*_dto.py`, `*_entity.py` 네이밍 사용 금지
- 라우터에 큰 변환/검증 로직 직접 구현 금지

## Migration Checklist

- 새 파일 생성 시 레이어에 맞는 접미사 사용
- import 경로가 새 파일명(`*_request_dto.py`, `*_response_dto.py`, `*_usecase.py`, `*_entity.py`)을 따르는지 확인
- `python -m compileall apps/ai_api/app` 로 최소 문법 검증
