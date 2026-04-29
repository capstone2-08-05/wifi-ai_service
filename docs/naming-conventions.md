# Naming Conventions

`rf-service` 코드 네이밍 규칙입니다.  
현재 기준은 `apps/ai_api/app` 레이어드 아키텍처를 우선으로 합니다.

## Core Rules

- **DTO 클래스**: `*RequestDto`, `*ResponseDto`
- **Entity 클래스**: `*Entity`
- **Usecase 파일**: `*_usecase.py`
- **Usecase 함수**: `*_usecase`
- **라우터 파일**: 리소스 중심 (`inference.py`, `sionna.py`)
- **인프라 실행기 파일**: 역할 중심 (`*_runner.py`, `*_gateway.py`)

## Layer Rules

- `api/routes`
  - FastAPI endpoint 정의만 둡니다.
  - 파일명은 도메인 리소스 기준으로 짧게 유지합니다.
  - 비즈니스 로직/변환 로직은 넣지 않습니다.

- `api/deps.py`
  - FastAPI 의존성 주입(`Depends(...)`)으로 호출되는 함수만 둡니다.
  - 라우트가 직접 호출하지 않고 FastAPI가 주입해주는 함수가 대상.
  - 예: `parse_inference_upload_request` (요청 파싱/검증 후 DTO 반환)

- `api/error_responses/`
  - OpenAPI 문서용 에러 응답 메타데이터만 둡니다 (런타임 동작에는 영향 없음).
  - 공통 schema/빌더는 `__init__.py`에, 라우트별 정의는 별도 파일로 분리합니다.
  - 예: `error_responses/sionna.py`, `error_responses/inference.py`

- `api/error_normalizers/`
  - 라우트에서 발생한 예외를 `AppError`로 정규화하는 함수만 둡니다.
  - 라우트별 파일로 분리합니다.
  - 예: `error_normalizers/sionna.py`, `error_normalizers/inference.py`

- `presentation/requests`
  - 내부 입력 DTO만 둡니다.
  - 파일명: `*_request_dto.py`
  - 예: `sionna_request_dto.py`, `inference_request_dto.py`

- `presentation/responses`
  - 내부 전용 응답 DTO + response 변환 함수를 둡니다.
  - 파일명: `*_response_dto.py`
  - 다른 서비스/프론트와 공유되는 응답 타입은 여기가 아니라 `packages/contracts/`에 둡니다.
  - 예: `sionna_response_dto.py` (`SionnaRunResponseDto` + `to_sionna_response`)

- `domain/entities`
  - 도메인 모델만 둡니다.
  - 파일명: `*_entity.py`
  - 클래스명: `*Entity`

- `usecases`
  - 유즈케이스 오케스트레이션만 둡니다.
  - 파일명: `*_usecase.py`
  - 함수명: `*_usecase`
  - 응답 객체 생성도 usecase의 책임 (얇은 빌더 함수를 별도 파일로 두지 않음).

- `infrastructure`
  - 외부 라이브러리/패키지 호출 어댑터를 둡니다.
  - `ai_runtime`: 모델 런타임 호출
  - `sionna`: Sionna 런타임 호출
  - 파일명은 `*_runner.py`, `*_gateway.py`를 사용합니다.

- `packages/contracts`
  - 다른 서비스/프론트와 공유되는 API 컨트랙트 타입을 둡니다.
  - Pydantic `BaseModel` 기반.
  - 예: `UnetInferenceResponse`, `YoloInferenceResponse`

## Naming Examples

- Request DTO: `SionnaRunRequestDto`, `InferenceUploadRequestDto`
- Response DTO (내부): `SionnaRunResponseDto`
- Response Contract (공용): `UnetInferenceResponse`, `YoloInferenceResponse`
- Entity: `SionnaRunPathsEntity`
- Usecase function: `run_sionna_usecase`, `run_unet_usecase`

## Prohibited Patterns

- DTO에 `Entity` 접미사 사용 금지
- Entity에 `Dto` 접미사 사용 금지
- 라우터 파일에 `*_dto.py`, `*_entity.py` 네이밍 사용 금지
- 라우터에 큰 변환/검증 로직 직접 구현 금지
- DTO 파일(`*_dto.py`)에 FastAPI 의존성 함수(`Depends`로 쓰이는 함수) 두기 금지 → `api/deps.py`로
- DTO 파일에 DTO 외 다른 코드(빌더/검증/파서) 두기 금지

## Migration Checklist

- 새 파일 생성 시 레이어에 맞는 접미사 사용
- import 경로가 새 파일명(`*_request_dto.py`, `*_response_dto.py`, `*_usecase.py`, `*_entity.py`)을 따르는지 확인
- `python -m compileall apps/ai_api/app` 로 최소 문법 검증
